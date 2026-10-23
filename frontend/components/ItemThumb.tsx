import type { ItemBrief } from "@/lib/types";

const ICONS: Record<string, string> = {
  음향: "🎤",
  촬영: "📷",
  영상: "📽",
  "전기·전원": "🔌",
};

export default function ItemThumb({ item, size = "md" }: { item: ItemBrief; size?: "sm" | "md" | "lg" }) {
  const cls =
    size === "lg" ? "aspect-[4/3] w-full" : size === "sm" ? "size-12 shrink-0" : "size-20 shrink-0";
  if (item.has_image) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={`/api/items/${item.id}/image?v=${item.image_version}`}
        alt={`${item.name} (${item.asset_code}) 사진`}
        className={`${cls} rounded-lg bg-navy-50 object-cover`}
      />
    );
  }
  return (
    <div
      role="img"
      aria-label={`${item.name} 기본 이미지`}
      className={`${cls} flex flex-col items-center justify-center rounded-lg bg-gradient-to-br from-navy-50 to-teal-50 text-navy-500`}
    >
      <span className={size === "lg" ? "text-6xl" : size === "sm" ? "text-xl" : "text-3xl"} aria-hidden>
        {ICONS[item.category] ?? "📦"}
      </span>
      {size === "lg" && <span className="mt-2 text-sm font-semibold">등록된 사진 없음</span>}
    </div>
  );
}
