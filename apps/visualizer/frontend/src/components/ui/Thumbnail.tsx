import { MATCH_CARD_NO_IMAGE } from '../../constants/strings';

interface ThumbnailProps {
  url: string;
  label: string;
  loaded: boolean;
  error: boolean;
  onLoad: () => void;
  onError: () => void;
  alignRight?: boolean;
  errorText?: string;
}

export function Thumbnail({ url, label, loaded, error, onLoad, onError, alignRight, errorText = MATCH_CARD_NO_IMAGE }: ThumbnailProps) {
  return (
    <div className="w-1/2 bg-gray-100 relative">
      {!loaded && !error && <div className="absolute inset-0 bg-gray-200 animate-pulse" />}
      {error ? (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-gray-400">
          {errorText}
        </div>
      ) : (
        <img
          src={url}
          alt={label}
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
          loading="lazy"
          onLoad={onLoad}
          onError={onError}
        />
      )}
      <div className={`absolute top-1 ${alignRight ? 'right-1' : 'left-1'} bg-black/60 text-white text-xs px-1.5 py-0.5 rounded`}>
        {label}
      </div>
    </div>
  );
}
