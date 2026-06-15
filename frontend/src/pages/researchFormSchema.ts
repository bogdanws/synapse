import { z } from 'zod'

import { ALLOWED_MODELS } from '../constants/models'

const allowedModelIds: string[] = ALLOWED_MODELS.map((m) => m.id)

export const researchFormSchema = z.object({
  topic: z.string().min(10, 'Topic must be at least 10 characters').max(2000),
  depth: z.enum(['shallow', 'standard', 'deep']),
  language: z.string(),
  models: z
    .object({
      scout: z.string(),
      scribe: z.string(),
      critic: z.string(),
    })
    .refine((vals) => Object.values(vals).every((v: string) => allowedModelIds.includes(v)), {
      message: 'Invalid model selection',
    }),
})

export type ResearchFormData = z.infer<typeof researchFormSchema>
