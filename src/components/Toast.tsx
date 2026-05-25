import { useEffect, useState } from "react";

export interface ToastMessage {
  id: number;
  text: string;
}

let _nextId = 0;
let _globalSetToasts: ((updater: (prev: ToastMessage[]) => ToastMessage[]) => void) | null = null;

export function showToast(text: string) {
  _globalSetToasts?.((prev) => [...prev, { id: ++_nextId, text }]);
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    _globalSetToasts = setToasts;
    return () => { _globalSetToasts = null; };
  }, []);

  return (
    <div className="toast-container" aria-live="polite">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDone={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDone }: { toast: ToastMessage; onDone: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDone, 3000);
    return () => clearTimeout(timer);
  }, [onDone]);

  return (
    <div className="toast" role="status">
      {toast.text}
    </div>
  );
}
