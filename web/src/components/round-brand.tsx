import Image from "next/image";
import Link from "next/link";

export function RoundBrand() {
  return <Link href="/" className="round-brand" aria-label="Tee time home">
    <Image src="/branding/tee-time-logo.png" alt="" width={70} height={45} unoptimized className="brand-logo" />
    <span>Tee time<span className="brand-dot">.</span></span>
  </Link>;
}
