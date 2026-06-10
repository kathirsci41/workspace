export type BundleStatus =
  | 'OK'
  | 'REVIEW_REQUIRED'
  | 'MISMATCH'
  | 'MISSING_DOCUMENTS'
  | 'BLOCKED';

export type SectionStatus =
  | 'PASS'
  | 'PARTIAL_PASS'
  | 'REVIEW_REQUIRED'
  | 'MISMATCH'
  | 'MISSING_DOCUMENTS'
  | 'BLOCKED';
