import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { api, setAccessToken } from '@/lib/api';

// Helper to set token if available (for NextAuth mode)
function useSetTokenIfAvailable() {
  const { data: session } = useSession();
  if (session?.accessToken) {
    setAccessToken(session.accessToken as string);
  }
}

export type InspirationStatus = 'pending' | 'analyzing' | 'analyzed' | 'error';

export interface InspirationLookItem {
  id: string;
  position: number;
  type: string;
  subtype: string | null;
  primary_color: string | null;
  colors: string[];
  pattern: string | null;
  material: string | null;
  style: string[];
  formality: string | null;
  season: string[];
  fit: string | null;
  description: string | null;
  confidence: number | null;
  matched_item_id: string | null;
}

export interface InspirationLook {
  id: string;
  status: InspirationStatus;
  error_message: string | null;
  photo_url: string | null;
  photo_medium_url: string | null;
  photo_thumbnail_url: string | null;
  created_at: string;
  updated_at: string;
  items: InspirationLookItem[];
}

export interface InspirationLookListResponse {
  looks: InspirationLook[];
}

// Partial update: only the fields the user actually edited should be sent, matching
// the backend's exclude_unset handling. `type` cannot be cleared; the other scalar
// fields can be cleared with null, and list fields default to [] rather than null.
export interface InspirationLookItemUpdate {
  type?: string;
  subtype?: string | null;
  primary_color?: string | null;
  colors?: string[];
  pattern?: string | null;
  material?: string | null;
  style?: string[];
  formality?: string | null;
  season?: string[];
  fit?: string | null;
  description?: string | null;
}

export function useInspirationLooks() {
  const { status } = useSession();
  useSetTokenIfAvailable();

  return useQuery({
    queryKey: ['inspirationLooks'],
    queryFn: () => api.get<InspirationLookListResponse>('/inspiration'),
    enabled: status !== 'loading',
  });
}

const ANALYZING_POLL_INTERVAL_MS = 3000;

export function useInspirationLook(lookId: string | undefined) {
  const { status } = useSession();
  useSetTokenIfAvailable();

  return useQuery({
    queryKey: ['inspirationLook', lookId],
    queryFn: () => api.get<InspirationLook>(`/inspiration/${lookId}`),
    enabled: !!lookId && status !== 'loading',
    // Analysis runs in the background worker, so poll until it lands rather than
    // leaving the user staring at a stale "pending" card.
    refetchInterval: (query) => {
      const data = query.state.data as InspirationLook | undefined;
      if (!data) return false;
      return data.status === 'pending' || data.status === 'analyzing'
        ? ANALYZING_POLL_INTERVAL_MS
        : false;
    },
    refetchIntervalInBackground: true,
  });
}

export function useUploadInspirationLook() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();

  return useMutation({
    mutationFn: (photo: File) => {
      if (session?.accessToken) {
        setAccessToken(session.accessToken as string);
      }
      const data = new FormData();
      data.append('image', photo);
      return api.postForm<InspirationLook>('/inspiration', data);
    },
    onSuccess: (look) => {
      queryClient.setQueryData(['inspirationLook', look.id], look);
      queryClient.invalidateQueries({ queryKey: ['inspirationLooks'] });
    },
  });
}

export function useUpdateInspirationLookItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      lookId,
      itemId,
      updates,
    }: {
      lookId: string;
      itemId: string;
      updates: InspirationLookItemUpdate;
    }) => api.patch<InspirationLookItem>(`/inspiration/${lookId}/items/${itemId}`, updates),
    onSuccess: (updatedItem, { lookId }) => {
      queryClient.setQueryData<InspirationLook | undefined>(['inspirationLook', lookId], (look) =>
        look
          ? {
              ...look,
              items: look.items.map((item) => (item.id === updatedItem.id ? updatedItem : item)),
            }
          : look
      );
    },
  });
}

export function useDeleteInspirationLook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (lookId: string) => api.delete<void>(`/inspiration/${lookId}`),
    onSuccess: (_data, lookId) => {
      queryClient.removeQueries({ queryKey: ['inspirationLook', lookId] });
      queryClient.invalidateQueries({ queryKey: ['inspirationLooks'] });
    },
  });
}
