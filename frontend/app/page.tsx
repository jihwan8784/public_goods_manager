import Header from "./components/Header";
import ProductCard from "./components/ProductCard";
import CustomerForm from "./components/CustomerForm";

const products = [
  { name: "동아고 후드티", price: 35000, color: "bg-blue-800" },
  { name: "텀블러", price: 15000, color: "bg-emerald-600" },
  { name: "에코백", price: 12000, color: "bg-amber-500" },
];

export default function Home() {
  return (
    <div className="min-h-full bg-zinc-50">
      <Header />
      <main className="mx-auto grid max-w-5xl gap-10 px-6 py-10">
        <section>
          <h2 className="mb-4 text-xl font-bold text-zinc-900">상품 목록</h2>
          <div className="grid gap-6 sm:grid-cols-3">
            {products.map((p) => (
              <ProductCard key={p.name} {...p} />
            ))}
          </div>
        </section>
        <CustomerForm />
      </main>
    </div>
  );
}
