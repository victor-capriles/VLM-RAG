/**
 * UI-related type definitions for the Vision RAG evaluation viewer
 */

/**
 * Available tabs in the application
 */
export type TabType = 'results' | 'dashboard';

/**
 * Filter options for the results view
 */
export type ModelFilter = string | 'all';
export type ContextFilter = 'all' | 'with_context' | 'without_context';
export type EmbeddingFilter = string | 'all';
export type ContextImpactFilter = 'all' | 'positive' | 'negative' | 'no_change' | 'evaluated';

/**
 * Application state interface for reactive state management
 */
export interface AppState {
  /** Currently selected model filter */
  selectedModel: ModelFilter;
  /** Currently selected context filter */
  selectedContext: ContextFilter;
  /** Currently selected embedding provider filter */
  selectedEmbedding: EmbeddingFilter;
  /** Currently selected context impact filter */
  selectedContextImpact: ContextImpactFilter;
  /** Whether filter panel is expanded */
  showFilters: boolean;
  /** Currently active tab */
  activeTab: TabType;
}

/**
 * Infinite scroll state management
 */
export interface InfiniteScrollState {
  /** Current limit of visible items */
  visibleItemsLimit: number;
  /** Whether more items are currently being loaded */
  isLoadingMore: boolean;
  /** Whether to show all items at once (disable infinite scroll) */
  showAllItems: boolean;
}

/**
 * Constants for infinite scroll behavior
 */
export const INFINITE_SCROLL_CONFIG = {
  /** Initial number of items to display */
  INITIAL_LIMIT: 50,
  /** Number of items to load per scroll trigger */
  ITEMS_PER_LOAD: 25,
  /** Root margin for intersection observer */
  ROOT_MARGIN: '100px'
} as const; 