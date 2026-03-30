import { MetadataRow, MetadataSection } from '../metadata';
import { ExifDataSection } from '../metadata/ExifDataSection';
import {
  LABEL_ADDED,
  LABEL_DATE_FOLDER,
  LABEL_FILENAME,
  LABEL_MEDIA_KEY,
  LABEL_SOURCE_FOLDER,
  LABEL_VISUAL_HASH,
  HASH_EXPLANATION,
  META_SECTION_BASIC_INFO,
  META_SECTION_CAPTION,
  META_SECTION_FILE_LOCATION,
  META_SECTION_IMAGE_ANALYSIS,
} from '../../constants/strings';
import type { InstagramImage } from '../../services/api';

interface ImageMetadataPanelProps {
  image: InstagramImage;
}

export function ImageMetadataPanel({ image }: ImageMetadataPanelProps) {
  return (
    <div className="space-y-4">
      <MetadataSection title={META_SECTION_BASIC_INFO}>
        <div className="space-y-2">
          <MetadataRow label={LABEL_FILENAME} value={image.filename} />
          <MetadataRow label={LABEL_MEDIA_KEY} value={image.key} />
          <MetadataRow label={LABEL_SOURCE_FOLDER} value={image.source_folder} />
          <MetadataRow label={LABEL_DATE_FOLDER} value={image.instagram_folder} />
          <MetadataRow label={LABEL_ADDED} value={new Date(image.crawled_at).toLocaleString()} />
        </div>
      </MetadataSection>

      {image.image_hash && (
        <MetadataSection title={META_SECTION_IMAGE_ANALYSIS}>
          <MetadataRow label={LABEL_VISUAL_HASH} value={image.image_hash} monospace />
          <p className="text-xs text-gray-500 mt-2">{HASH_EXPLANATION}</p>
        </MetadataSection>
      )}

      <ExifDataSection exifData={image.exif_data} />

      {image.description && (
        <MetadataSection title={META_SECTION_CAPTION}>
          <p className="text-sm text-gray-800 whitespace-pre-wrap">
            {image.description}
          </p>
        </MetadataSection>
      )}

      <MetadataSection title={META_SECTION_FILE_LOCATION}>
        <code className="text-xs text-gray-600 break-all">
          {image.local_path}
        </code>
      </MetadataSection>
    </div>
  );
}
