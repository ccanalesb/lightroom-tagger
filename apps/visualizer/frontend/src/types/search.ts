import type { components } from './api.gen'

/** Generated from backend OpenAPI — see ADR-0013. */
type ChatSearchMessageSchema =
  components['schemas']['ChatSearchRequest.2fa5250.ChatSearchMessage']

export type ChatSearchMessage = Pick<ChatSearchMessageSchema, 'role'> &
  Partial<Pick<ChatSearchMessageSchema, 'content' | 'tool_calls' | 'tool_call_id'>>

type ChatSearchRequestSchema = components['schemas']['ChatSearchRequest.2fa5250']

export type ChatSearchRequest = Pick<ChatSearchRequestSchema, 'message'> &
  Partial<
    Omit<ChatSearchRequestSchema, 'message' | 'messages'> & {
      messages?: ChatSearchMessage[] | null
    }
  >

export type ChatSearchResultImage =
  components['schemas']['ChatSearchResponse.2fa5250.ChatSearchResultImage']

type ChatSearchResponseSchema = components['schemas']['ChatSearchResponse.2fa5250']

/** NL/semantic paths omit ``messages`` / ``assistant_message`` on the wire. */
export type ChatSearchResponse = Pick<
  ChatSearchResponseSchema,
  'search_mode' | 'total' | 'images'
> &
  Partial<
    Pick<
      ChatSearchResponseSchema,
      'filters' | 'metadata' | 'messages' | 'assistant_message'
    >
  >
