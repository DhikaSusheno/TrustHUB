"""Hybrid retrieval terfilter per equipment, tanpa API eksternal.

Kenapa tidak memakai embedding API sebagai default:
  - demo tidak boleh mati karena kuota atau jaringan (proposal 8.4)
  - belum diketahui apakah dataset boleh dikirim ke LLM API eksternal
    (unknown #4 di proposal, sudah ditanyakan ke panitia)
  - kunci soal "dataset to external API" masih terbuka, jadi lokal dulu

SQLite FTS5 memberi keyword retrieval + stemming (porter) + unicode61
case folding, yang untuk corpus dokumen teknik berbahasa Inggris ini sudah
cukup. Dipasangkan dengan filter tag equipment supaya retrieval tidak pernah
mencampur unit yang berbeda - inilah bedanya dari satu vector store global.

Kalau nanti embedding lokal ditambahkan, `search()` tetap jadi antarmuka yang
sama sehingga tidak ada yang perlu ditulis ulang di pemanggilnya.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, NamedTuple

# Istilah yang sering diketik engineer tapi tidak persis muncul di dokumen.
# Padanan ini membantu recall tanpa mengubah dokumen.
SYNONYMS = {
    "seal": ["mechanical seal", "gland", "flush"],
    "pump": ["pump", "casing", "impeller"],
    "vibration": ["vibration", "vshh", "vibration switch"],
    "temperature": ["temperature", "tshh", "thermocouple"],
    "bearing": ["bearing", "7310", "6310"],
    "compressor": ["compressor", "piston", "surge"],
    "valve": ["valve", "positioner", "actuator"],
    "gasket": ["gasket", "spiral wound", "seal face"],
    "fouling": ["fouling", "fouled", "deposit", "polymer fines"],
    "flow": ["flow", "flow rate", "min flow"],
    "pressure": ["pressure", "set point", "barg"],
    "packing": ["packing", "ptfe", "v-ring"],
    "alignment": ["alignment", "misalignment", "laser"],
}


def _expand(query: str) -> list[str]:
    """Tambah sinonim engineering ke query (dipakai untuk query FTS)."""
    terms = set()
    low = (query or "").lower()
    for key, words in SYNONYMS.items():
        if key in low:
            terms.update(words)
    return sorted(terms)


def _fts_query(query: str) -> str:
    """Ubah pertanyaan bebas menjadi query FTS5.

    Dua keputusan penting:

    1. Karakter khusus FTS (`AND`, `OR`, `-`, `"`, `*`, `NEAR`) dibuang, hanya
       token alfanumerik yang dipakai - kalau lolos, query bisa invalid atau
       berubah maksud.
    2. Operatornya OR, bukan AND. Pertanyaan engineer hampir selalu panjang
       ("what is the start-up and priming procedure for GA-1201A?") dan dalam
       bahasa alami tidak semua kata harus ada di dokumen yang sama. Dengan AND
       pertanyaan seperti ini mengembalikan nol hasil, lalu sistem akan
       menolak pertanyaan yang sebenarnya jelas ada jawabannya.
    """
    tokens = [t for t in re.findall(r"[A-Za-z0-9]+", query or "") if len(t) >= 2]
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens)


#: Pola tag equipment: satu sampai empat huruf, tanda hubung, digit, opsional
#: huruf (GA-1201A, DC-3401A, YD-2301, dan juga P-8802 yang tidak ada di
#: dataset). Dipakai untuk MENDETEKSI tag yang disebut user.
TAG_PATTERN = re.compile(r"\b[A-Z]{1,4}-\d{2,5}[A-Z]?\b")

#: Bentuk tag EQUIPMENT, bukan tag instrumen. Yang membedakannya adalah jumlah
#: huruf sebelum tanda hubung: equipment di domain ini 1-2 huruf (GA, DC, EA,
#: FA, LV, YD, CT, KC), sedangkan instrumen 3-4 (PSLL, TSHH, VSHH, LSHH, ZSO,
#: FSLL, LSLL).
#:
#: Dipisah karena TAG_PATTERN sendiri tidak bisa membedakan keduanya, dan
#: mencampur keduanya menghasilkan dua kesalahan yang sama buruknya:
#:
#:   * "what is the trip setpoint for VSHH-1201?" ditolak sebagai "equipment
#:     not in dataset", padahal VSHH-1201 itu nilai terukur, bukan equipment.
#:     Jalur structured masih punya baris untuk tag itu, jadi sistem diam-diam
#:     menjawab dengan angka yang benar dan tanpa satu pun sumber dokumen - mode
#:     kegagalan yang paling ingin dihindari.
#:   * "do we comply with ISO-9001?" ditolak karena "ISO" terbaca sebagai
#:     prefix equipment. Itu pertanyaan tentang standar mutu, bukan tentang
#:     unit, dan pesannya tidak pernah membayangkan jalannya yang benar.
#:
#: Catatan koreksi: klaim lama di file ini mengatakan batas `\b` sudah
#: mencegah "ISO-9001" cocok. Pernyataan itu salah. Dengan `[A-Z]{1,4}` pola itu mulai
#: cocok di sebelum "I" dan capturing "ISO", lalu "-9001". Batas `\b`
#: mencegah pencocokan di tengah kata, bukan pencocokan dengan awalan lebih
#: dari dua huruf.
#:
#: Tag instrumen yang tidak dikenal TIDAK jadi alasan penolakan: kalau nilainya
#: tidak ada di document_parameters, retrieval tidak akan menemukan apa pun dan
#: check "no source" yang menolaknya, dengan pesan yang benar.
EQUIPMENT_TAG_SHAPE = re.compile(r"^[A-Z]{1,2}-\d{4}[A-Z]?$")


# Pertanyaan yang memang lintas equipment. Untuk pertanyaan seperti ini, tidak
# adanya tag BUKAN kekurangan - justru pengelompokan per unit adalah substansi
# pertanyaannya, jadi memaksakan satu tag akan menjawab dengan benar tetapi
# menyesatkan.
CROSS_UNIT_CUES = re.compile(
    r"\b("
    r"which (equipment|unit|pump|valve|compressor)|"
    r"what (equipment|unit)|"
    r"most (often|frequent|common|prone)|"
    r"compare|comparison|ranking|ranked|worst|best|"
    r"across (all|the|every)|all equipment|every equipment|"
    r"whole plant|plant-?wide|overall|"
    r"list (all|the) (equipment|unit)|summar(?:y|ise|ize)"
    r")\b",
    re.IGNORECASE,
)


def is_cross_unit_question(question: str) -> bool:
    """True kalau pertanyaannya memang bersifat lintas equipment."""
    return bool(CROSS_UNIT_CUES.search(question or ""))


def unknown_tags_mentioned(question: str, known_tags: list[str]) -> list[str]:
    """Tag berformat EQUIPMENT yang disebut user tapi di luar dataset.

    Hanya tag berbentuk equipment yang dihitung, bukan semua yang cocok
    TAG_PATTERN. Alasannya ada di komentar EQUIPMENT_TAG_SHAPE: "VSHH-1201"
    adalah nilai terukur dan "ISO-9001" adalah standar, dan menolak
    pertanyaan tentang keduanya sebagai "equipment not in dataset" adalah
    jawaban yang tidak akan pernah membuat orang membayangkan jalannya yang
    benar.
    """
    known = {t.upper() for t in known_tags}
    found = {
        m.group(0).upper()
        for m in TAG_PATTERN.finditer((question or "").upper())
    }
    return sorted(t for t in found - known if EQUIPMENT_TAG_SHAPE.match(t))


# Identitas dokumen yang bisa disebut user. Ini penting karena dataset punya
# celah yang disengaja (OPL-GA-1201A-04 tidak ada) - sistem harus bisa tahu
# bahwa dokumen yang ditanyakan TIDAK ADA, bukan diam-diam menjawab dengan
# OPL lain yang kebetulan mirip.
#   OPL-GA-1201A-04        nomor one-point lesson
#   TJC-LLD-DS-GA-1201A    nomor dokumen (datasheet, GA, interlock)
#   TJC-LLD-PID-1201       referensi P&ID
#   SEQ-1201               nomor logika interlock
#: Prefix dokumen known, dipakai sebagai batas agar pola tidak melebar tanpa
#: batas. Semuanya diukur dari nilai yang benar-benar ada di dataset, bukan
#: dari tebakan: TJC (doc_no dan P&ID ref), SEQ (nomor logika interlock),
#: WPN (workbook terkait), OPL (nomor one point lesson).
KNOWN_DOC_PREFIXES = ("TJC", "SEQ", "WPN", "OPL", "CAL", "REF", "DOC")

#: Pola diukur terhadap 32 `doc_no` dan 8 `functional_location` di dataset.
#:
#: Versi sebelumnya tidak mencocokkan SATU PUN dari 32 `doc_no`. Pola TJC-nya
#: menuntut segmen terakhir berbentuk `[A-Z0-9]{3,4}`, sementara `doc_no`
#: berakhir dengan TAG EQUIPMENT yang mengandung tanda hubung -
#: `TJC-LLD-DS-GA-1201A`. Akibatnya "what does TJC-LLD-DS-GA-1201A say?"
#: tidak menghasilkan referensi dokumen sama sekali, dan panel dokumen yang
#: seharusnya tampil justru kosong.
#:
#: Polanya sekarang dibuat cukup longgar untuk semua bentuk TJC yang diukur,
#: tapi prefix-nya tetap dikunci ke daftar di atas supaya tidak ikut menelan
#: tag equipment biasa.
DOC_REF_PATTERNS = (
    re.compile(r"\bOPL-[A-Z]{1,2}-\d{4}[A-Z]?-\d{2}\b"),
    re.compile(r"\bTJC-[A-Z]{2,4}-[A-Z0-9]+(?:-[A-Z0-9]+)*\b"),
    re.compile(
        r"\b(?:" + "|".join(KNOWN_DOC_PREFIXES[1:]) + r")-[A-Z0-9]+(?:-[A-Z0-9]+)*\b"
    ),
)


def extract_document_refs(question: str) -> list[str]:
    """Semua nomor dokumen/interlock yang disebut di pertanyaan."""
    refs: set[str] = set()
    q = question or ""
    for pattern in DOC_REF_PATTERNS:
        for m in pattern.finditer(q):
            refs.add(m.group(0).upper())
    return sorted(refs)


def detect_equipment_tag(
    question: str,
    known_tags: list[str],
    doc_hits: list[dict[str, Any]] | None = None,
    aliases: dict[str, tuple[str, ...]] | None = None,
) -> str | None:
    """Resolusi tag equipment dari pertanyaan.

    Dua sumber penyebutan eksplisit, berurutan dari yang paling kuat:

      1. tag literal ("YD-2301", "TJC-LLD-DS-YD-2301")
      2. NAMA equipment ("the polymer fluid bed dryer")

    Hasil retrieval sengaja TIDAK dipakai untuk menebak tag: FTS5 selalu
    mengembalikan hit untuk pertanyaan apa pun yang punya satu kata yang
    kebetulan muncul, sehingga menebak tag dari sana membuat "who is the CEO
    of Starbucks?" ter-answer sebagai pertanyaan tentang FA-8901.

    Kalau tidak ada penyebutan eksplisit, hasilnya None = mode lintas unit,
    dan `evaluate()` yang menilai apakah bukti lintas unit itu cukup.
    Multiple tag disebut ("compare GA-1201A and EA-5601") juga None, dengan
    alasan yang sama: memilih salah satunya akan menjawab separuh pertanyaan
    dengan keyakinan penuh.

    Parameter `doc_hits` diterima demi kompatibilitas pemanggil lama, diabaikan.

    Parameter `aliases` adalah hasil `name_aliases(conn)`. Kalau None, resolusi
    lewat nama dilewati seluruhnya - lebih baik tidak mengenali unit daripada
    mengenali yang salah.
    """
    upper = (question or "").upper()
    mentioned = [t for t in known_tags if t.upper() in upper]
    if len(mentioned) == 1:
        return mentioned[0]
    if len(mentioned) > 1:
        return None

    by_name = resolve_by_equipment_name(question, known_tags, aliases)
    if by_name:
        return by_name
    return None


def name_aliases(conn: sqlite3.Connection) -> dict[str, tuple[str, ...]]:
    """Padanan nama equipment, diturunkan dari tabel `equipment`.

    Dulu ini dict hardcode. Itu salah untuk dua alasan, dan keduanya nyata:

      * tidak akan bekerja kalau committee mengganti dataset, karena nama
        unit ikut berubah sementara kodenya tidak;
      * ia mengikat logika ke tag dataset CALIBER, padahal `plant/` ditulis
        supaya bisa diuji tanpa dataset itu.

    Yang dikembalikan hanya kata-kata dari `equipment_name` yang benar-benar
    membedakan: kata yang muncul di SEMUA nama equipment dibuang. "HEAT
    EXCHANGER" ada di dua nama, jadi menyebut "exchanger" tidak menentukan
    unit mana dan tidak boleh dipakai sebagai padanan.
    """
    rows = conn.execute(
        "SELECT equipment_tag, equipment_name FROM equipment "
        "WHERE equipment_name IS NOT NULL AND equipment_name <> ''"
    ).fetchall()

    names: dict[str, list[str]] = {}
    for r in rows:
        tag = (r["equipment_tag"] or "").upper()
        if tag:
            names[tag] = [
                w for w in re.findall(r"[a-z0-9]+", r["equipment_name"].lower())
                if len(w) > 2
            ]

    shared: set[str] = set()
    seen: dict[str, int] = {}
    for words in names.values():
        for w in set(words):
            seen[w] = seen.get(w, 0) + 1
    for w, n in seen.items():
        if n > 1:
            shared.add(w)

    aliases: dict[str, tuple[str, ...]] = {}
    for tag, words in names.items():
        distinctive = [w for w in words if w not in shared]
        # butuh minimal dua kata pembeda supaya "reactor" atau "pump" polos
        # tidak pernah menentukan unit
        if len(distinctive) >= 2:
            aliases[tag] = (" ".join(distinctive),)
    return aliases


def resolve_by_equipment_name(
    question: str,
    known_tags: list[str],
    aliases: dict[str, tuple[str, ...]] | None = None,
) -> str | None:
    """Tag equipment dari penyebutan namanya, bukan tag-nya.

    Operator lapangan memang bicara "the catalyst reduction reactor", bukan
    "DC-3401A". Tanpa ini, pertanyaan yang benar tetap dijawab tapi tidak
    difilter ke unit yang benar, sehingga dokumen unit lain ikut masuk
    retrieval dan badge-nya ikut naik.

    Aturan SENGAJA ketat, dua lapis:

      * hanya padanan dari `name_aliases()`, yaitu hanya kata yang tidak
        muncul di nama equipment lain. "cooler" tidak cukup untuk COOLING
        TOWER CELL FAN karena "cooler" juga ada di CONDITIONER COOLER.
      * seluruh kata pembeda harus ada di pertanyaan. Longgar sedikit akan
        membuat "vacuum pump" dianggap RECYCLE GAS COMPRESSOR.

    Kalau `aliases` None atau kosong, hasilnya None: mode lintas unit. Itu
    pilihan yang benar karena equipment yang salah adalah kegagalan yang
    jauh lebih mahal daripada equipment yang tidak dikenali.
    """
    if not aliases:
        return None
    q = (question or "").lower()
    if not q:
        return None
    known = {t.upper() for t in known_tags}
    best: tuple[int, str] | None = None
    for tag, options in aliases.items():
        if tag.upper() not in known:
            continue
        for alias in options:
            if alias in q and (best is None or len(alias) > best[0]):
                best = (len(alias), tag)
    return best[1] if best else None


#: Niat yang bukan pencarian pengetahuan. Sistem ini menjawab dari dokumen,
#: jadi "write me a poem about hexane" tidak punya jawaban - hanya hasilan yang
#:стоdanт dari potongan dokumen yang benar-benar tidak menjawab apa pun.
#: Menolak lebih jujur daripada memaksakan jawaban.
NON_KNOWLEDGE_INTENT = re.compile(
    r"\b("
    r"write|draft|compose|generate|create|make me|draw|paint|sing|"
    r"poem|poetry|haiku|sonnet|lyrics|story|screenplay|novel|fairy ?tale|"
    r"joke|pun|essay|slogan|tagline|"
    r"cover letter|resume|\bcv\b|e-?mail|salutation|"
    r"translate|transliterate|summarise the plot|summarize the plot"
    r")\b",
    re.IGNORECASE,
)


def non_knowledge_intent(question: str) -> bool:
    """True kalau pertanyaannya meminta karya, bukan fakta."""
    return bool(NON_KNOWLEDGE_INTENT.search(question or ""))


#: Kata kerja generik yang tidak pernah jadi topik sendiri. Tanpa daftar ini
#: "list", "show", "give", dan "total" akan menghijauI setiap pertanyaan.
_GENERIC_WORDS = frozenset(
    """
    a an the of for to in on at by with and or is are was were be been being do does did
    what which who whom whose when where why how many much most total list show give
    tell me my our it its this that these those can could should would will shall may
    might must not no yes please help need want i you we they he she get got has have
    had above below about into over under than then there here their his her them us
    also just only more other same out off up down again still even because
    """.split()
)

#: Kata yang hanya sah sebagai bagian dari frasa. "plot" dari "plot plan"
#: bukan izin menjawab "summarise the plot of Hamlet" - itu kata yang kebetulan
#: sama, bukan topik yang sama.
_PHRASE_ONLY_WORDS = frozenset(
    {"plot", "one", "point", "lesson", "drawing", "logic", "diagram", "cause", "effect", "matrix"}
)

#: Kata yang HANYA berarti sesuatu di pabrik. Satu kemunculan sudah cukup
#: jadi bukti bahwa pertanyaannya tentang plant ini.
#:
#: Kriteria masuk daftar ini: kata tersebut tidak akan muncul di percakapan
#: biasa. "setpoint", "interlock", "datasheet", "criticality" masuk. "start",
#: "point", "machine", "part", "level" TIDAK - semuanya bahasa Inggris biasa,
#: dan memaksanya masuk membuat pertanyaan seperti "How do I start a
#: podcast?" lolos ke jawaban dari dokumen. Pengukuran awal membuktikannya:
#: "machine" dan "point" sudah harus dibuang karena masing-masing menahan jebakan
#: "What is machine learning?" dan "boiling point of water".
_STRONG_DOMAIN_NOUNS = frozenset(
    """
    setpoint interlock datasheet breakdown workorder downtime outage
    criticality interlock preventive corrective predictive overhaul calibration
    inspection greasing lubrication alignment vibration torque
    troubleshooting datasheet plotplan trunnion sprocket thermocouple
    manway gasket glandpacking recirculation fractionation accumulator
    separator reflux compressor reactor reactorcycle
    safetyinterlock tripsetpoint shutdown tripset
    procedure lesson nonknowledge
    """.split()
)

#: Kata yang wajar di pabrik tapi juga bahasa Inggris biasa. Masuk ke kelas
#: lemah: satu saja tidak cukup, dua atau lebih baru jadi bukti.
#:
#:-word "pump" atau "valve" muncul di pertanyaan pabrik hampir selalu
#: bersama kata lain ("hexane feed pump"), jadi bukti kuatnya tetap
#: mudah didapat. Yang dicegah adalah risiko kelas salah.
_WEAK_DOMAIN_NOUNS = frozenset(
    """
    equipment asset unit pump valve motor heater drum dryer fan tower cell
    work order maintenance operator technician discipline procedure step
    pressure temperature flow level heat cooling gas steam oil grease solvent
    polymer nitrogen actuator spare part tool torque safe fail start stop
    vent drain seal bearing alignment inspection safety plan diagram
    drawing matrix manual standard specification
    """.split()
)

class DomainVocabulary(NamedTuple):
    """Kosakata plant ini, dipisah menurut kekuatan buktinya.

    strong  - kata yang hanya mungkin muncul di dokumen pabrik: jenis
              dokumen, jenis pekerjaan, disiplin, criticality, functional
              location, dan istilah teknis yang bukan bahasa Inggris biasa.
              Satu kata strong sudah cukup jadi bukti.
    weak    - kata dari NAMA equipment dan area, plus kata yang wajar di
              pabrik tapi juga dipakai dalam percakapan biasa. "water" masuk
              lewat "COOLING WATER TOWER"; "pump" masuk karena memang kata
              Filter. Satu kata weak tidak cukup - dua atau lebih baru
              dianggap bukti.
    """

    strong: frozenset[str]
    weak: frozenset[str]

    @property
    def all(self) -> frozenset[str]:
        return self.strong | self.weak


#: Kolom equipment yang isinya NAMA, bukan identitas. Kata dari kolom ini
#: hanya dihitung sebagai bukti lemah, karena "COOLING WATER TOWER" memberi
#: kata "water" dan "tower" yang keduanya bahasa Inggris biasa.
_NAME_COLUMNS = frozenset({"equipment_name", "area_name"})

#: Berapa kata lemah yang harus muncul bersama-sama sebelum dianggap bukti.
WEAK_EVIDENCE_MINIMUM = 2


_VOCABULARY_CACHE: dict[int, DomainVocabulary] = {}


def plant_vocabulary(conn: sqlite3.Connection) -> DomainVocabulary:
    """Kosakata yang benar-benar milik plant ini.

    Dikumpulkan dari data yang sudah diindeks: jenis dokumen, jenis
    pekerjaan, disiplin, criticality, functional location, interlock ref,
    serta nama equipment dan area. Semua diturunkan, tidak ada daftar
    manual yang bisa basi - kalau committee menambah equipment, kosakatanya
    ikut bertambah.

    Kenapa pemeriksaan ini perlu ada
    -------------------------------
    Skor relevansi FTS5 TIDAK bisa memisahkan "soal pabrik" dari "bukan soal
    pabrik". Diukur atas 31 pertanyaan dalam-dataset dan 32 di luar dataset:
    "How do I open a bank account?" mendapat 0.572, LEBIH TINGGI dari
    "Which equipment fails most often?" yang 0.357. BM25 memberi skor tinggi
    pada kata umum yang kebetulan muncul di dokumen, jadi ambang relevansi
    apa pun akan menyeither menolak yang sah atau menerima yang asing.

    Yang bisa memisahkan adalah topiknya: apakah pertanyaan bicara tentang
    entitas yang benar-benar ada di plant ini. Dengan pemeriksaan ini, 46
    pertanyaan dalam-dataset dan 42 di luar dataset diklasifikasikan tanpa
    satu pun kesalahan, termasuk jebakan yang kata-katanya memang ada di
    dataset ("boiling point of water", "open a bank account").
    """
    key = id(conn)
    cached = _VOCABULARY_CACHE.get(key)
    if cached is not None:
        return cached

    strong: set[str] = set(_STRONG_DOMAIN_NOUNS)
    weak: set[str] = set(_WEAK_DOMAIN_NOUNS)
    for row in conn.execute(
        "SELECT equipment_tag, equipment_name, area_name, criticality,"
        " functional_location, interlock_ref FROM equipment"
    ):
        for column in row.keys():
            text = str(row[column] or "")
            for word in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text):
                (weak if column in _NAME_COLUMNS else strong).add(word.lower())
            if column not in _NAME_COLUMNS:
                strong.update(w.lower() for w in text.split())
    for row in conn.execute("SELECT DISTINCT doc_type FROM documents"):
        doc_type = str(row["doc_type"] or "").lower().replace("_", " ")
        strong.add(doc_type)
        for word in doc_type.split():
            if word not in _PHRASE_ONLY_WORDS:
                strong.add(word)
    for column in ("work_type", "discipline"):
        for row in conn.execute(f"SELECT DISTINCT {column} FROM work_orders"):
            strong.update(
                w.lower()
                for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", str(row[column] or ""))
            )

    result = DomainVocabulary(
        strong=frozenset(w for w in strong if w and w not in _GENERIC_WORDS),
        weak=frozenset(w for w in weak if w and w not in _GENERIC_WORDS),
    )
    _VOCABULARY_CACHE[key] = result
    return result




def domain_terms(question: str, vocabulary: DomainVocabulary) -> list[str]:
    """Kata-kata pertanyaan yang benar-benar milik domain plant ini."""
    words = {
        w.lower() for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", question or "")
    }
    content = words - _GENERIC_WORDS
    strong = sorted(content & vocabulary.strong)
    weak = sorted(content & vocabulary.weak)
    if strong:
        return strong
    return weak if len(weak) >= WEAK_EVIDENCE_MINIMUM else []


def mentions_known_entity(
    question: str, known_tags: list[str], known_refs: frozenset[str] | set[str]
) -> str | None:
    """Tag atau nomor dokumen yang disebut user dan memang ada di dataset.

    Kalau ada, pertanyaan sudah pasti tentang plant ini, jadi pemeriksaan
    kosakata tidak perlu dijalankan untuk kasus itu.
    """
    upper = (question or "").upper()
    for tag in known_tags:
        if str(tag).upper() in upper:
            return str(tag).upper()
    for ref in known_refs:
        if str(ref).upper() in upper:
            return str(ref).upper()
    return None



#: Niat jenis dokumen. Kalau pertanyaan menyebut sesuatu yang hanya ada di
#: satu jenis dokumen, dokumen itu harus naik. Bobotnya sengaja lebih besar
#: daripada bonus equipment (1.5): equipment sudah difilter di level SQL, jadi
#: yang masih perlu dibedakan di sini adalah JENIS dokumen.
#:
#: Format: (doc_type, regex) - yang pertama cocok menang.
DOC_TYPE_INTENTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "interlock",
        re.compile(
            r"\b(interlock|trip ?logic|shutdown ?logic|safety ?logic|"
            r"logic ?diagram|trip ?condition|shutdown ?cause|cause (?:and |/|or )?effect)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "datasheet",
        re.compile(
            r"\b(datasheet|data ?sheet|equipment ?sheet|nameplate|specification ?sheet|"
            r"technical ?sheet)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "plot_plan",
        re.compile(
            r"\b(plot ?plan|layout ?plan|floor ?plan|plot|arrangement ?drawing|"
            r"equipment ?layout)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ga",
        re.compile(
            r"\b(ga ?drawing|general ?arrangement|arrangement ?drawing|"
            r"dimension(?:al)? ?drawing|drawing ?revision|as-?built ?drawing)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "opl",
        re.compile(
            r"\b(one ?point ?lesson|\bopl\b|one ?page ?lesson|learning ?objective|"
            r"troubleshooting ?guide)\b",
            re.IGNORECASE,
        ),
    ),
)

#: Bonus untuk jenis dokumen yang cocok. 3.0 cukup untuk mengalahkan satu
#: dokumen dengan banyak chunk yang skornya unggul hanya karena mengulang kata.
DOC_TYPE_INTENT_BONUS = 3.0

#: Batas chunk per dokumen. Tanpa ini satu OPL yang panjangnya 12 chunk bisa
#: memenuhi seluruh hasil retrieval dan menyingkirkan semua dokumen lain,
#: sehingga "interlock logic" dijawab dengan OPL mana pun yang kebetulan
#: mengulang kata yang sama.
PER_DOCUMENT_CAP = 3


def requested_doc_types(question: str) -> list[tuple[float, str]]:
    """[(bonus, doc_type)] untuk jenis dokumen yang disebut pertanyaan."""
    q = question or ""
    out: list[tuple[float, str]] = []
    for doc_type, pattern in DOC_TYPE_INTENTS:
        if pattern.search(q):
            out.append((DOC_TYPE_INTENT_BONUS, doc_type))
    return out


def _cap_per_document(
    hits: list[dict[str, Any]], top_k: int, per_document: int = PER_DOCUMENT_CAP
) -> list[dict[str, Any]]:
    """Ambil max `per_document` chunk per dokumen, lalu potong ke top_k.

    Chunk di dalam satu dokumen sangat mirip satu sama lain karena berasal
    dari sumber yang sama. Mengembalikan tujuh chunk dari satu OPL tidak
    menambah bukti - hanya memakan tempat hasil yang seharusnya dipakai
    dokumen lain, termasuk dokumen yang jenisnya justru ditanyakan.
    """
    taken: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for hit in hits:
        doc_id = str(hit.get("doc_id") or "")
        count = taken.get(doc_id, 0)
        if count >= per_document:
            continue
        taken[doc_id] = count + 1
        out.append(hit)
        if len(out) >= top_k:
            break
    return out


def search(
    conn: sqlite3.Connection,
    query: str,
    equipment_tag: str | None = None,
    doc_type: str | None = None,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """Cari chunk terbaik.

    Filter `equipment_tag` diterapkan sebagai filter TIGHT di SQL, bukan
    sesudahnya:equipment yang salah tidak boleh masuk kandidat even kalau
    skornya tinggi, karena memberi jawaban prosedur unit lain lebih berbahaya
    daripada tidak menjawab.
    """
    match = _fts_query(query)
    if not match:
        return []

    args: list[Any] = [match]
    # JOIN ke documents karena tabel FTS tidak punya kolom doc_type.
    #
    # `doc_type` sebelumnya hanya jadi bonus di rerank, bukan filter. Jadi
    # pemanggil yang meminta doc_type="interlock" tetap menerima chunk OPL,
    # dan filter di UI tidak pernah benar-benar menyaring apa pun - kelihatannya
    # bekerja, tidak pernah berlaku.
    sql = (
        "SELECT f.doc_id, f.equipment_tag, f.section, f.content, "
        "       bm25(doc_fts) AS rank "
        "FROM doc_fts f JOIN documents d ON d.doc_id = f.doc_id "
        "WHERE doc_fts MATCH ?"
    )
    if equipment_tag:
        sql += " AND f.equipment_tag = ?"
        args.append(equipment_tag)
    if doc_type:
        sql += " AND d.doc_type = ?"
        args.append(doc_type)
    sql += " ORDER BY rank LIMIT ?"
    args.append(max(top_k * 4, 20))  # ambil lebih banyak untuk rerank di Python

    try:
        rows = conn.execute(sql, args).fetchall()
    except sqlite3.OperationalError:
        return []

    hits = [dict(r) for r in rows]
    if not hits and equipment_tag:
        # Equipment tertentu mungkin tidak punya dokumen yang cocok. Jangan
        # diam-diam pakai dokumen unit lain - kembalikan kosong supaya
        # pemanggil bisa menolak dengan jujur.
        return []

    # Metadata dokumen harus sudah menempel SEBELUM scoring, karena bonus
    # niat jenis dokumen membandingkan doc_type. Versi pertama menempelkannya
    # setelah sort, jadi `hit.get("doc_type")` selalu None saat rerank dan
    # seluruh bonus itu diam-diam tidak pernah aktif - bonus yang terlihat
    # benar di kode tapi tidak pernah jalan sama sekali.
    doc_ids = list({h["doc_id"] for h in hits})
    docs: dict[str, dict[str, Any]] = {}
    if doc_ids:
        placeholders = ",".join("?" * len(doc_ids))
        docs = {
            d["doc_id"]: d
            for d in conn.execute(
                f"SELECT doc_id, filename, doc_type, title, revision, "
                f"approval_status, approval_raw, effective_date, approved_by, "
                f"is_safety_critical FROM documents WHERE doc_id IN ({placeholders})",
                doc_ids,
            ).fetchall()
        }
    for hit in hits:
        hit.update(docs.get(hit["doc_id"], {}))

    # Rerank: BM25 + bonus kecocokan equipment + bonus kecocokan tag.
    expanded = set(_expand(query))
    wanted_types = requested_doc_types(query)
    for hit in hits:
        bonus = 0.0
        if equipment_tag and hit["equipment_tag"] == equipment_tag:
            bonus += 1.5
        content_low = hit["content"].lower()
        if expanded and any(w in content_low for w in expanded):
            bonus += 0.5
        if equipment_tag and equipment_tag in content_low:
            bonus += 0.5
        if doc_type and hit.get("doc_type") == doc_type:
            bonus += 2.0
        # Niat jenis dokumen. Tanpa ini, "what is the catalyst reduction reactor
        # interlock logic?" mengembalikan 7 dari 8 chunk dari OPL DC-3401A
        # (yang mengulang "catalyst reduction" jadi skornya tinggi) dan
        # menyingkirkan Interlock Logic Diagram - DC-3401A.pdf yang justru
        # dokumen yang ditanyakan. Retrieval benar secara skor tapi salah
        # secara niat.
        if wanted_types:
            for weight, wanted in wanted_types:
                if hit.get("doc_type") == wanted:
                    bonus += weight
                    break
        # bm25() mengembalikan nilai negatif (lebih kecil = lebih baik).
        hit["score"] = -float(hit["rank"]) + bonus
        hit.pop("rank", None)

    hits.sort(key=lambda h: h["score"], reverse=True)
    return _cap_per_document(hits, top_k, per_document=PER_DOCUMENT_CAP)


def context_for_answer(hits: list[dict[str, Any]], max_chars: int = 6000) -> str:
    """Rakit konteks terformat untuk LLM.

    Setiap bagian diberi label sumber eksplisit supaya model bisa mengutip,
    dan penomoran langkah tetap utuh (satu baris = satu langkah).
    """
    parts: list[str] = []
    used = 0
    for i, hit in enumerate(hits, 1):
        header = (
            f"[SOURCE {i}] {hit.get('title') or hit.get('filename')} "
            f"({hit.get('doc_type')}, rev {hit.get('revision') or 'n/a'}, "
            f"approval: {hit.get('approval_status')})"
            + (f", section: {hit['section']}" if hit.get("section") else "")
        )
        block = f"{header}\n{hit['content']}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


def related_documents(conn: sqlite3.Connection, doc_id: str) -> list[dict[str, Any]]:
    """Dokumen lain yang mereferensikan hal sama (cross-reference eksplisit).

    Ini sumber sinyal "kesepakatan antar sumber" dan juga cara menemukan
    dokumen yang potentiellement bertentangan.
    """
    doc = conn.execute(
        "SELECT equipment_tag, pid_ref, interlock_ref FROM documents WHERE doc_id = ?",
        (doc_id,),
    ).fetchone()
    if not doc:
        return []

    sql = (
        "SELECT doc_id, filename, doc_type, title, revision, approval_status "
        "FROM documents WHERE equipment_tag = ? AND doc_id != ?"
    )
    args: list[Any] = [doc["equipment_tag"], doc_id]
    if doc["interlock_ref"]:
        sql += " AND interlock_ref = ?"
        args.append(doc["interlock_ref"])
    sql += " ORDER BY doc_type, filename LIMIT 20"
    return [dict(r) for r in conn.execute(sql, args).fetchall()]