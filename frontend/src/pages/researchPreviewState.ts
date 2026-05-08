import { z } from 'zod'

/**
 * Shape of the router state pushed from `/research/new` when the user
 * advances to the preview screen. Lives in its own module (rather than next
 * to the page component) so the router can validate it in `beforeLoad`
 * without crossing the Fast Refresh boundary that requires component files
 * to export only components.
 */
export const previewStateSchema = z.object({
  formData: z.object({
    topic: z.string(),
    depth: z.enum(['shallow', 'standard', 'deep']),
    language: z.string(),
    models: z.record(z.string(), z.string()),
  }),
  subQuestions: z.array(z.string()).min(1),
})

export type PreviewState = z.infer<typeof previewStateSchema>
