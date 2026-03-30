import { Modal, ModalFooter, ModalHeader } from '../modal';
import {
  MODAL_CLOSE,
  MODAL_TITLE_IMAGE_DETAILS,
} from '../../constants/strings';
import type { InstagramImage } from '../../services/api';
import { thumbnailUrl as buildThumbUrl } from '../../utils/imageUrl';
import { SingleMatchSection } from './SingleMatchSection';
import { ImageMetadataPanel } from './ImageMetadataPanel';

interface ImageDetailsModalProps {
  image: InstagramImage;
  onClose: () => void;
}

export function ImageDetailsModal({ image, onClose }: ImageDetailsModalProps) {
  const imgThumbUrl = buildThumbUrl('instagram', image.key);

  return (
    <Modal onClose={onClose}>
      <ModalHeader title={MODAL_TITLE_IMAGE_DETAILS} onClose={onClose} />

      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden">
              <img
                src={imgThumbUrl}
                alt={image.filename}
                className="w-full h-full object-contain"
              />
            </div>
            <SingleMatchSection image={image} />
          </div>

          <ImageMetadataPanel image={image} />
        </div>
      </div>

      <ModalFooter>
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
        >
          {MODAL_CLOSE}
        </button>
      </ModalFooter>
    </Modal>
  );
}
