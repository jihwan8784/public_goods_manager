import Image from "next/image";

/** 서비스 로고 (public/logo.svg). 글자와 함께 쓰므로 스크린리더에는 숨긴다. */
export default function Logo({ size = 32, className = "" }: { size?: number; className?: string }) {
  return <Image src="/logo.svg" alt="" aria-hidden width={size} height={size} className={className} priority />;
}
