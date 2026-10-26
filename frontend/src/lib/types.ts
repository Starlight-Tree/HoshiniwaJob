// バックエンド（backend/app/schemas.py）の応答の型
export type Code = { code: number; name: string };
export type OccupationGroup = { category: string; items: Code[] };
export type Master = {
  areas: Code[];
  stations: Code[];
  occupations: OccupationGroup[];
  employments: Code[];
};

export type RecruitSummary = {
  id: number;
  corporate: string | null;
  category: string | null;
  salary: number | null; // 1 年俸制 / 2 月給制 / 3 日給制 / 4 時給制
  pay_min: number | null;
  pay_max: number | null;
  comment1: string | null;
  note1: string | null;
  formfile: string | null;
  areas: string[];
  stations: string[];
  occupations: string[];
  employments: string[];
};

export type RecruitDetail = RecruitSummary & {
  profile: string | null;
  place: string | null;
  note2: string | null;
  note3: string | null;
  comment2: string | null;
  comment3: string | null;
  workday: string | null;
  insurance: string | null;
  start_time: string | null;
  end_time: string | null;
};

export type RecruitPage = {
  total: number;
  page: number;
  per_page: number;
  last_page: number;
  items: RecruitSummary[];
};

export type FacetCount = { code: number; count: number };
export type Facets = {
  total: number;
  areas: FacetCount[];
  stations: FacetCount[];
  occupations: FacetCount[];
  employments: FacetCount[];
};

export type User = { id: number; email: string; last_name: string | null; first_name: string | null };
export type Session = { token: string; user: User };

export type Garden = { id: number; email: string; corporate: string };
export type GardenSession = { token: string; garden: Garden };
export type GardenSummary = { corporate: string; email: string; displayed: number; hidden: number };
