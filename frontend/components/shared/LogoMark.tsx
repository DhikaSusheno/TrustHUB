// The mark: a hex nut with a clean bore.
//
// The hexagon is the literal hardware in a plant and the literal "hub" in
// TrustHUB. The bore is the one source the rest of the documents agree with.
// Two shapes, one colour, no gradient, so it stays legible at 16px in a browser
// tab and at 28px in the nav without needing a second drawing.
//
// It lives in shared/ because it used to be copy-pasted into LeftNav and again
// into the landing header. Two copies of a logo is how a logo ends up meaning
// two things, and app/icon.svg had already drifted to a green shield, which
// also asserted a TRUSTED verdict. An icon should not rule on anything.
export default function LogoMark({
  className = "h-full w-full",
}: {
  className?: string;
}) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={`${className} text-blue-500`}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinejoin="round"
    >
      <path d="M12 3 19.79 7.5 19.79 16.5 12 21 4.21 16.5 4.21 7.5Z" />
      <circle cx="12" cy="12" r="3.6" />
    </svg>
  );
}