import { configureStore } from '@reduxjs/toolkit'
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import { useDispatch, useSelector } from 'react-redux'

export type LabelField = 'is_xx' | 'is_xxx'
export interface LabelAnalysis {
  status: 'not_analyzed' | 'disabled' | 'complete' | 'needs_review' | 'error'
  mode?: 'off' | 'review' | 'apply'
  suggestions?: Partial<Record<LabelField, boolean | null>>
  scores?: Partial<Record<LabelField, number>>
  manual_overrides?: Partial<Record<LabelField, boolean | null>>
  projection_pending?: boolean
  stale?: boolean
  error?: string
}
interface Conversation {
  id: string; label: string; type: string; source_file?: string; date?: string
  is_xx: boolean; is_xxx: boolean; is_favorite?: boolean
  is_midjourney_style?: boolean; llm_failed?: boolean
  all_user_prompts?: string; all_ai_responses?: string
  turns?: { speaker: string; text: string; turn_index?: number; model?: string }[]
  image_aspects?: Record<string, string[]>
  tags?: string[]; custom_tags?: string[]; mj_flags?: string[]
  label_analysis?: LabelAnalysis
}
interface LabelUpdate {
  id: string
  label_analysis: LabelAnalysis
  is_xx?: boolean
  is_xxx?: boolean
}

export const labelsApi = createApi({
  reducerPath: 'labelsApi',
  baseQuery: fetchBaseQuery({ baseUrl: '/api/' }),
  tagTypes: ['Conversation'],
  endpoints: builder => ({
    getConversation: builder.query<Conversation, string>({
      query: id => `conversation/${encodeURIComponent(id)}`,
      providesTags: (_result, _error, id) => [{ type: 'Conversation', id }],
    }),
    setLabel: builder.mutation<LabelUpdate, { id: string; field: LabelField; value: boolean | null }>({
      query: ({ id, field, value }) => ({
        url: `conversation/${encodeURIComponent(id)}/${field === 'is_xx' ? 'xx' : 'xxx'}`,
        method: 'PATCH',
        body: { [field]: value },
      }),
      invalidatesTags: (_result, _error, { id }) => [{ type: 'Conversation', id }],
    }),
  }),
})

export const store = configureStore({
  reducer: { [labelsApi.reducerPath]: labelsApi.reducer },
  middleware: getDefaultMiddleware => getDefaultMiddleware().concat(labelsApi.middleware),
})
export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
export const useAppDispatch = useDispatch.withTypes<AppDispatch>()
export const useAppSelector = useSelector.withTypes<RootState>()
export const { useGetConversationQuery, useSetLabelMutation } = labelsApi
