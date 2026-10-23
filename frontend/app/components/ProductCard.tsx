type Props = {
  name: string;
  price: number;
  color: string;
};

export default function ProductCard({ name, price, color }: Props) {
  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
      <div className={`h-40 ${color}`} />
      <div className="p-4">
        <h3 className="text-lg font-semibold text-zinc-900">{name}</h3>
        <p className="mt-1 text-zinc-600">{price.toLocaleString("ko-KR")}원</p>
      </div>
    </div>
  );
}
