"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { itemUrl, qrPng, qrSvg } from "@/lib/qr";
import type { ItemBrief } from "@/lib/types";
import { btn } from "./ui";

/** 관리자용: 개별 물품 상세 페이지로 연결되는 QR (주소만 담김, 권한·상태 변경 없음) */
export default function QrPanel({ item }: { item: ItemBrief }) {
  const [svg, setSvg] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const u = itemUrl(item.id);
    qrSvg(u)
      .then((s) => {
        setUrl(u);
        setSvg(s);
      })
      .catch(() => setError("QR 코드를 만들지 못했습니다."));
  }, [item.id]);

  async function download() {
    try {
      const data = await qrPng(url, 800);
      const a = document.createElement("a");
      a.href = data;
      a.download = `QR-${item.asset_code}.png`;
      a.click();
    } catch {
      setError("QR 이미지를 저장하지 못했습니다.");
    }
  }

  return (
    <div className="grid gap-3 sm:grid-cols-[10rem_1fr] sm:items-center">
      <div className="mx-auto w-40 rounded-lg border border-navy-100 bg-white p-2">
        {svg ? (
          <div role="img" aria-label={`${item.asset_code} 상세 페이지 QR 코드`} dangerouslySetInnerHTML={{ __html: svg }} />
        ) : (
          <div className="aspect-square animate-pulse bg-navy-50" />
        )}
      </div>
      <div className="grid gap-2 text-sm">
        <p className="text-navy-700">
          휴대전화 기본 카메라로 찍으면 이 물품의 상세 페이지가 열립니다. QR에는 주소만 담겨 있어 권한이나 대여 상태를 바꾸지 않습니다.
        </p>
        <p className="break-all font-mono text-xs text-navy-500">{url}</p>
        {error && (
          <p role="alert" className="font-semibold text-rose-800">
            {error}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={download} disabled={!url} className={btn.secondary}>
            PNG 다운로드
          </button>
          <Link href={`/admin/qr?ids=${item.id}`} className={btn.secondary}>
            라벨 인쇄
          </Link>
        </div>
      </div>
    </div>
  );
}
