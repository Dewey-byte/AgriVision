import React, { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const MIN_ZOOM = 1;
const MAX_ZOOM = 6;
const CLICK_ZOOM = 2.5;
const WHEEL_STEP = 0.22;

function clamp(n, lo, hi) {
  return Math.min(hi, Math.max(lo, n));
}

export default function ZoomableImage({ src, alt }) {
  const [open, setOpen] = useState(false);
  const [scale, setScale] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const viewportRef = useRef(null);
  const viewRef = useRef({ scale: 1, tx: 0, ty: 0 });
  const dragRef = useRef({ active: false, moved: false, x: 0, y: 0, tx: 0, ty: 0 });

  viewRef.current = { scale, tx, ty };

  const resetView = useCallback(() => {
    setScale(1);
    setTx(0);
    setTy(0);
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    setScale(1);
    setTx(0);
    setTy(0);
  }, []);

  const zoomAt = useCallback((clientX, clientY, nextScale) => {
    const el = viewportRef.current;
    if (!el) return;
    const { scale: cur, tx: curTx, ty: curTy } = viewRef.current;
    const clamped = clamp(nextScale, MIN_ZOOM, MAX_ZOOM);
    if (clamped <= MIN_ZOOM) {
      setScale(1);
      setTx(0);
      setTy(0);
      return;
    }
    if (clamped === cur) return;
    const rect = el.getBoundingClientRect();
    const mx = clientX - rect.left - rect.width / 2;
    const my = clientY - rect.top - rect.height / 2;
    const ratio = clamped / cur;
    setScale(clamped);
    setTx(mx - (mx - curTx) * ratio);
    setTy(my - (my - curTy) * ratio);
  }, []);

  const zoomTowardCenter = useCallback((nextScale) => {
    const el = viewportRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, nextScale);
  }, [zoomAt]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") close();
      if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        zoomTowardCenter(viewRef.current.scale + 0.5);
      }
      if (e.key === "-" || e.key === "_") {
        e.preventDefault();
        zoomTowardCenter(viewRef.current.scale - 0.5);
      }
      if (e.key === "0") resetView();
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, close, resetView, zoomTowardCenter]);

  useEffect(() => {
    if (!open) return undefined;
    const el = viewportRef.current;
    if (!el) return undefined;
    const onWheel = (e) => {
      e.preventDefault();
      const dir = e.deltaY > 0 ? -1 : 1;
      zoomAt(e.clientX, e.clientY, viewRef.current.scale + dir * WHEEL_STEP);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [open, zoomAt]);

  const onPointerDown = (e) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = {
      active: true,
      moved: false,
      x: e.clientX,
      y: e.clientY,
      tx,
      ty,
    };
  };

  const onPointerMove = (e) => {
    const drag = dragRef.current;
    if (!drag.active) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    if (!drag.moved && dx * dx + dy * dy > 16) drag.moved = true;
    if (scale <= 1) return;
    setTx(drag.tx + dx);
    setTy(drag.ty + dy);
  };

  const onPointerUp = (e) => {
    const drag = dragRef.current;
    const wasDrag = drag.moved;
    drag.active = false;
    drag.moved = false;
    if (wasDrag) return;
    if (scale <= 1.05) {
      zoomAt(e.clientX, e.clientY, CLICK_ZOOM);
    } else {
      resetView();
    }
  };

  const zoomed = scale > 1.05;

  return (
    <>
      <button type="button" className="frame-zoom-trigger" onClick={() => setOpen(true)} title="Click to zoom">
        <img className="frame-img" src={src} alt={alt} />
        <span className="frame-zoom-hint">Click to zoom in or out</span>
      </button>

      {open &&
        createPortal(
          <div className="frame-zoom-overlay" role="dialog" aria-modal="true" aria-label={alt || "Zoomed frame"} onClick={close}>
            <div className="frame-zoom-toolbar" onClick={(e) => e.stopPropagation()}>
              <span className="muted">{Math.round(scale * 100)}%</span>
              <button type="button" className="ghost" onClick={() => zoomTowardCenter(scale - 0.5)} disabled={scale <= MIN_ZOOM}>
                −
              </button>
              <button type="button" className="ghost" onClick={() => zoomTowardCenter(scale + 0.5)} disabled={scale >= MAX_ZOOM}>
                +
              </button>
              <button type="button" className="ghost" onClick={resetView} disabled={scale <= MIN_ZOOM}>
                Reset
              </button>
              <button type="button" className="ghost" onClick={close}>
                Close
              </button>
            </div>
            <div
              ref={viewportRef}
              className={`frame-zoom-viewport${zoomed ? " is-zoomed" : ""}`}
              onClick={(e) => e.stopPropagation()}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={() => {
                dragRef.current.active = false;
                dragRef.current.moved = false;
              }}
            >
              <img
                src={src}
                alt={alt}
                draggable={false}
                style={{ transform: `translate(${tx}px, ${ty}px) scale(${scale})` }}
              />
            </div>
            <p className="frame-zoom-help">Click to zoom in · click again to zoom out · scroll or drag when zoomed</p>
          </div>,
          document.body
        )}
    </>
  );
}
