"use client";

import { useState } from "react";

type Customer = { name: string; email: string; product: string };

const PRODUCTS = ["동아고 후드티", "텀블러", "에코백"];

export default function CustomerForm() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [product, setProduct] = useState(PRODUCTS[0]);
  const [submitted, setSubmitted] = useState<Customer | null>(null);

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // 지금은 서버 없이 입력값을 아래에 보여주기만 한다
    setSubmitted({ name, email, product });
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
          className="rounded-md bg-blue-900 px-4 py-2 font-semibold text-white hover:bg-blue-800"
        >
          등록하기
        </button>
      </form>

      {submitted && (
        <div className="mt-4 rounded-md bg-zinc-100 p-4 text-sm text-zinc-800">
          <p>이름: {submitted.name}</p>
          <p>이메일: {submitted.email}</p>
          <p>관심 상품: {submitted.product}</p>
        </div>
      )}
    </section>
  );
}
