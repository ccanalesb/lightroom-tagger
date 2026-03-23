import { MetadataSection } from './MetadataSection'
import { MetadataRow } from './MetadataRow'
import {
  META_SECTION_EXIF_DATA,
  MSG_NO_EXIF_DATA,
  LABEL_GPS_COORDINATES,
  LABEL_DATE_TAKEN,
  LABEL_CAMERA,
  LABEL_LENS,
  LABEL_ISO,
  LABEL_APERTURE,
  LABEL_SHUTTER_SPEED,
} from '../../constants/strings'

interface ExifData {
  latitude?: number
  longitude?: number
  date_time_original?: string
  device_id?: string
  lens_model?: string
  iso?: number
  aperture?: string
  shutter_speed?: string
}

interface ExifDataSectionProps {
  exifData?: ExifData
}

export function ExifDataSection({ exifData }: ExifDataSectionProps) {
  const hasData = exifData && Object.keys(exifData).length > 0

  return (
    <MetadataSection title={META_SECTION_EXIF_DATA}>
      {hasData ? (
        <div className="space-y-2">
          {exifData?.latitude !== undefined && exifData?.longitude !== undefined && (
            <MetadataRow
              label={LABEL_GPS_COORDINATES}
              value={`${exifData.latitude.toFixed(6)}, ${exifData.longitude.toFixed(6)}`}
            />
          )}
          {exifData?.date_time_original && (
            <MetadataRow label={LABEL_DATE_TAKEN} value={exifData.date_time_original} />
          )}
          {exifData?.device_id && (
            <MetadataRow label={LABEL_CAMERA} value={exifData.device_id} />
          )}
          {exifData?.lens_model && (
            <MetadataRow label={LABEL_LENS} value={exifData.lens_model} />
          )}
          {exifData?.iso !== undefined && (
            <MetadataRow label={LABEL_ISO} value={String(exifData.iso)} />
          )}
          {exifData?.aperture && (
            <MetadataRow label={LABEL_APERTURE} value={exifData.aperture} />
          )}
          {exifData?.shutter_speed && (
            <MetadataRow label={LABEL_SHUTTER_SPEED} value={exifData.shutter_speed} />
          )}
        </div>
      ) : (
        <p className="text-sm text-gray-500 italic">{MSG_NO_EXIF_DATA}</p>
      )}
    </MetadataSection>
  )
}
