"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** 브라우저 기본 dialog: Esc로 닫기, 포커스 가두기를 기본 제공 */
export default function Dialog({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="dialog-title"
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-xl p-0 text-navy-900 shadow-xl"
    >
      {open && (
        <div className="p-5">
          <h2 id="dialog-title" className="text-lg font-bold">
            {title}
          </h2>
          <div className="mt-4">{children}</div>
        </div>
      )}
    </dialog>
  );
}
