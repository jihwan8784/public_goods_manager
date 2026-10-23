import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="text-center">
        <p className="text-sm font-semibold text-teal-700">404</p>
        <h1 className="mt-1 text-2xl font-bold text-navy-900">페이지를 찾을 수 없습니다</h1>
        <Link href="/" className="mt-4 inline-block font-semibold text-teal-800 underline">
          홈으로 이동
        </Link>
      </div>
    </main>
  );
}
