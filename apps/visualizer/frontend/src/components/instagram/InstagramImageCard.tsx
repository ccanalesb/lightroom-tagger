import { useState } from 'react';
import type { InstagramImage } from '../../services/api';
import { INSTAGRAM_ERROR_PLACEHOLDER, MSG_CLICK_FOR_DETAILS } from '../../constants/strings';
import { thumbnailUrl as buildThumbUrl } from '../../utils/imageUrl';

interface InstagramImageCardProps {
  image: InstagramImage;
  onClick: () => void;
}

export function InstagramImageCard({ image, onClick }: InstagramImageCardProps) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const thumbnailUrl = buildThumbUrl('instagram', image.key);

  return (
    <div
      className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow group bg-white cursor-pointer"
      onClick={onClick}
    >
      <div className="aspect-square bg-gray-100 relative">
        {!loaded && !error && (
          <div className="absolute inset-0 bg-gray-200 animate-pulse" />
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
            <span className="text-xs text-gray-400">{INSTAGRAM_ERROR_PLACEHOLDER}</span>
          </div>
        )}
        <img
          src={thumbnailUrl}
          alt={image.filename}
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`}
          loading="lazy"
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
        />
        {image.total_in_post > 1 && (
          <div className="absolute top-1 right-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
            {image.image_index}/{image.total_in_post}
          </div>
        )}
        {image.matched_catalog_key && (
          <div className="absolute top-1 left-1 w-3 h-3 rounded-full bg-green-500 border border-white" title={`Matched: ${image.matched_catalog_key}`} />
        )}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <span className="text-white text-sm font-medium">
            {MSG_CLICK_FOR_DETAILS}
          </span>
        </div>
      </div>
      <div className="p-2">
        <div className="flex items-start justify-between gap-1">
          <div className="flex flex-col min-w-0">
            <p
              className="text-xs font-medium text-gray-900 truncate"
              title={image.instagram_folder}
            >
              {image.instagram_folder}
            </p>
            <p
              className="text-[10px] text-gray-500 uppercase truncate"
              title={image.source_folder}
            >
              {image.source_folder}
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-0.5">
          {new Date(image.crawled_at).toLocaleDateString()}
        </p>
      </div>
    </div>
  );
}
