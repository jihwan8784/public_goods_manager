import QRCode from "qrcode";

export function itemUrl(itemId: number): string {
  const base = (process.env.NEXT_PUBLIC_SITE_URL || window.location.origin).replace(/\/+$/, "");
  return `${base}/items/${itemId}`;
}

export async function qrSvg(url: string): Promise<string> {
  return QRCode.toString(url, { type: "svg", margin: 1, errorCorrectionLevel: "M" });
}

export async function qrPng(url: string, width = 600): Promise<string> {
  return QRCode.toDataURL(url, { width, margin: 2, errorCorrectionLevel: "M" });
}
