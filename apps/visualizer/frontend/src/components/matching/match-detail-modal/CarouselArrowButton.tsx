interface CarouselArrowButtonProps {
  label: string;
  glyph: string;
  onClick: () => void;
}

export function CarouselArrowButton({ label, glyph, onClick }: CarouselArrowButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="w-8 h-8 flex items-center justify-center rounded-full border text-lg border-border text-text hover:bg-surface"
    >
      {glyph}
    </button>
  );
}
