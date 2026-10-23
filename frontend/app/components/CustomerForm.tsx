"use client";

import { useCallback, useEffect, useState } from "react";

type Customer = { id: number; name: string; email: string; product: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL;
const PRODUCTS = ["동아고 후드티", "텀블러", "에코백"];

export default function CustomerForm() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [product, setProduct] = useState(PRODUCTS[0]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [sending, setSending] = useState(false);

  const loadCustomers = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/customers`);
      if (!res.ok) throw new Error(`서버 응답 ${res.status}`);
      setCustomers(await res.json());
    } catch (e) {
      setError(`고객 목록을 불러오지 못했어요: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    // 화면이 열릴 때 등록된 고객 목록 불러오기
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadCustomers();
  }, [loadCustomers]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setMessage("");
    setError("");
    setSending(true);
    try {
      const res = await fetch(`${API_URL}/customers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, product }),
      });
      if (!res.ok) throw new Error(`서버 응답 ${res.status}`);
      setMessage("등록되었습니다!");
      setName("");
      setEmail("");
      setProduct(PRODUCTS[0]);
      await loadCustomers();
    } catch (e) {
      setError(`등록하지 못했어요: ${(e as Error).message}`);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-bold text-zinc-900">고객 등록</h2>
      <form onSubmit={handleSubmit} className="mt-4 grid gap-4">
        <label className="grid gap-1 text-sm text-zinc-700">
          이름
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900"
          />
        </label>
        <label className="grid gap-1 text-sm text-zinc-700">
          이메일
          <input
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900"
          />
        </label>
        <label className="grid gap-1 text-sm text-zinc-700">
          관심 상품
          <select
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-zinc-900"
          >
            {PRODUCTS.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={sending}
          className="rounded-md bg-blue-900 px-4 py-2 font-semibold text-white hover:bg-blue-800 disabled:opacity-60"
        >
          {sending ? "등록 중..." : "등록하기"}
        </button>
      </form>

      {message && <p className="mt-4 font-semibold text-emerald-700">{message}</p>}
      {error && <p className="mt-4 font-semibold text-red-600">{error}</p>}

      <h3 className="mt-8 text-lg font-bold text-zinc-900">등록된 고객</h3>
      {customers.length === 0 ? (
        <p className="mt-2 text-sm text-zinc-500">아직 등록된 고객이 없어요.</p>
      ) : (
        <ul className="mt-2 divide-y divide-zinc-200 text-sm">
          {customers.map((c) => (
            <li key={c.id} className="flex flex-wrap gap-x-4 py-2 text-zinc-800">
              <span className="font-semibold">{c.name}</span>
              <span className="text-zinc-500">{c.email}</span>
              <span>{c.product}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
