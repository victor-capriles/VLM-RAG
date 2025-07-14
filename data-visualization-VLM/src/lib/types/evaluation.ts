/**
 * Evaluation-related type definitions for the Vision RAG system
 */

/**
 * Raw result from the Vision RAG evaluation pipeline
 */
export interface RawResult {
  /** Unique identifier for the validation item */
  validation_id: string;
  /** Name of the model used for evaluation */
  model_name: string;
  /** Provider used for embeddings (e.g., 'cohere', 'openclip') */
  embedding_provider: string;
  /** Whether this result includes context from similar images */
  with_context: boolean;
  /** URL or path to the image being evaluated */
  image_url: string;
  /** The actual question being asked about the image */
  real_question: string;
  /** Majority answer from crowd-sourced validation */
  crowd_majority: string;
  /** Array of similar images found in the database */
  similar_images: any[]; // TODO: Define proper type for similar images
  /** The prompt template used for this evaluation */
  prompt_used: string;
  /** The LLM's response to the question */
  llm_response: string;
  /** Error message if the evaluation failed */
  error: string | null;
  /** Time taken to process this evaluation in seconds */
  processing_time: number;
}

/**
 * Grouped result combining with_context and without_context evaluations
 * for the same validation item, model, and embedding provider
 */
export interface GroupedResult {
  /** Unique identifier for this grouped result */
  id: string;
  /** Unique identifier for the validation item */
  validation_id: string;
  /** Name of the model used for evaluation */
  model_name: string;
  /** Provider used for embeddings */
  embedding_provider: string;
  /** URL or path to the image being evaluated */
  image_url: string;
  /** The actual question being asked about the image */
  real_question: string;
  /** Majority answer from crowd-sourced validation */
  crowd_majority: string;
  /** Result when context from similar images was provided */
  with_context: RawResult | null;
  /** Result when no context was provided */
  without_context: RawResult | null;
}

/**
 * Evaluation categories for scoring responses
 */
export type EvaluationCategory = 
  | 'directly_answered'    // 3 points
  | 'inferable'           // 2 points  
  | 'missing_incorrect'   // 1 point
  | 'hallucination';      // 0 points

/**
 * Progress statistics for evaluation completion
 */
export interface EvaluationProgress {
  /** Number of evaluations completed */
  current: number;
  /** Total number of evaluations possible */
  total: number;
  /** Completion percentage (0-100) */
  percentage: number;
} 