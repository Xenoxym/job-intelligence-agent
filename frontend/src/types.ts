export type Ranking = {
  score: number;
  base_score: number;
  decision: string;
  components: Record<
    string,
    { score: number; explanation: string; weight: number }
  >;
  strengths: string[];
  gaps: string[];
  reasons: string[];
  feedback_adjustment: number;
  feedback_explanation: {
    feature: string;
    value: string;
    observations: number;
    delta: number;
    outcomes: string[];
  }[];
};
export type Preparation = {
  resume_variant: string;
  fit_rationale: string[];
  strengths: string[];
  gaps: string[];
  screening_answers: Record<
    string,
    { answer: unknown; source: string | null; needs_review: boolean }
  >;
  unresolved: string[];
  cover_letter: string;
  company_notes: string;
  review_checklist: string[];
};
export type Job = {
  id: number;
  company: string;
  title: string;
  location: string;
  work_mode: string;
  status: string;
  source: string;
  apply_url: string;
  description: string;
  is_demo: boolean;
  posted_at: string | null;
  discovered_at: string;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  salary_interval: string | null;
  ranking: Ranking;
  analysis: {
    role_family: string;
    seniority: string;
    years_required: number | null;
    skills: string[];
    responsibilities: string[];
    required_qualifications: string[];
    preferred_qualifications: string[];
    authorization_language: string[];
  };
  preparation?: Preparation | null;
  sources?: {
    id: number;
    source: string;
    source_url: string;
    external_id: string;
    raw: unknown;
  }[];
  history?: { id: number; status: string; note: string; created_at: string }[];
};
export type Run = {
  id: number;
  source: string;
  status: string;
  discovered: number;
  deduplicated: number;
  ranked: number;
  errors: number;
  message: string;
  duration_ms: number;
};
export type Stats = {
  total: number;
  statuses: Record<string, number>;
  feedback_count: number;
  runs: Run[];
};
