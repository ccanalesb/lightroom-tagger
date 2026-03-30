import { MATCH_DETAIL_VISION_REASONING } from '../../../constants/strings';

interface VisionReasoningNoteProps {
  visionReasoning: string;
}

export function VisionReasoningNote({ visionReasoning }: VisionReasoningNoteProps) {
  return (
    <p className="text-sm text-gray-700 border-l-4 border-purple-200 pl-3 py-1 bg-gray-50 rounded-r">
      <span className="font-medium text-gray-800">{MATCH_DETAIL_VISION_REASONING}: </span>
      {visionReasoning}
    </p>
  );
}
