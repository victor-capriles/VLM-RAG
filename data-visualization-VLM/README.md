# Vision Language Model (VLM) Evaluation Dashboard

A comprehensive SvelteKit web application for evaluating and analyzing Vision Language Model responses. This tool provides an interactive dashboard for scoring model performance, analyzing response quality, and comparing different models and embedding providers across various metrics.

## Features

### 🔍 **Evaluation System**

- **4-Point Scoring Scale**: Rate responses as Direct (3pts), Inferable (2pts), Missing/Incorrect (1pt), or Hallucination (0pts)
- **Interactive Scoring**: Click category buttons to evaluate each response
- **Context Impact Analysis**: Compare performance with and without context
- **Progress Tracking**: Save and resume evaluations with export/import functionality

### 📊 **Analytics Dashboard**

- **Performance Metrics**: Track accuracy rates by model and embedding provider
- **Category Analysis**: Identify which models produce the most Direct responses or Hallucinations
- **Text Length Analytics**: Monitor response conciseness and verbosity patterns
- **Similarity Scoring**: ChromaDB distance-based similarity ratings with color coding
- **Visual Progress Bars**: Easy-to-read charts showing category distributions

### 🎯 **Conciseness Monitoring**

- **Word Count Tracking**: Automatic word counting for all responses
- **Conciseness Categories**:
  - Ideal (10-50 words) - Green
  - Brief (<10 words) - Yellow
  - Verbose (50-100 words) - Orange
  - Long (100-150 words) - Red
  - Excessive (>150 words) - Purple
- **Length Impact Analysis**: Understand how response length affects quality

### 🔧 **Data Management**

- **File Upload**: Upload `.jsonl` files containing evaluation results
- **Advanced Filtering**: Filter by model, context type, embedding provider
- **Infinite Scroll**: Efficiently handle large datasets
- **Export Progress**: Save evaluations with scores and analytics
- **Data Validation**: Robust error handling and data integrity checks

### 🎨 **User Interface**

- **Responsive Design**: Works seamlessly on desktop and mobile
- **Visual Similarity Indicators**: Color-coded distance ranges
- **Interactive Modals**: Full-screen image viewing
- **Sortable Columns**: Click headers to sort by different metrics
- **Real-time Updates**: Live filtering and sorting

## Data Format

The application expects JSONL files where each line contains a JSON object with the following structure:

```json
{
  "validation_id": "string",
  "model_name": "string",
  "embedding_provider": "string",
  "with_context": boolean,
  "image_url": "string",
  "real_question": "string",
  "crowd_majority": "string",
  "similar_images": ["array", "of", "image", "urls"],
  "prompt_used": "string",
  "llm_response": "string",
  "error": "string|null",
  "processing_time": number,
  "chroma_distance": number
}
```

### Key Fields

- `validation_id`: Unique identifier for grouping related evaluations
- `model_name`: Name of the LLM model being evaluated
- `embedding_provider`: Provider used for embedding generation (e.g., "cohere", "openai", "voyage")
- `with_context`: Boolean indicating if similar images were provided as context
- `image_url`: URL to the query image
- `real_question`: The question being asked about the image
- `crowd_majority`: The expected/correct answer
- `similar_images`: Array of URLs to context images (empty for without_context entries)
- `llm_response`: The model's response (null if error occurred)
- `error`: Error message if processing failed
- `processing_time`: Time taken to process the request in seconds
- `chroma_distance`: ChromaDB similarity distance score

## Evaluation Categories

### Scoring System (4-Point Scale)

- **🎯 Direct (3 points)**: Response directly and accurately answers the question
- **🔍 Inferable (2 points)**: Answer can be reasonably inferred from the response
- **❌ Missing/Incorrect (1 point)**: Response is incomplete or factually wrong
- **🚫 Hallucination (0 points)**: Response contains fabricated or contradictory information

### Similarity Ranges (ChromaDB Distance)

- **🟢 Very Similar (0.0-0.2)**: Extremely close matches
- **🔵 Similar (0.2-0.5)**: Good similarity matches
- **🟠 Moderate Similarity (0.5-1.0)**: Reasonable matches
- **🔴 Poor Similarity (>1.0)**: Distant or poor matches

## Getting Started

### Prerequisites

- Node.js (version 18 or higher)
- npm, yarn, pnpm, or bun

### Installation

1. Clone or download this repository
2. Install dependencies:

```bash
npm install
```

### Development

Start the development server:

```bash
npm run dev
```

The application will be available at `http://localhost:5173`

### Building for Production

Build the application:

```bash
npm run build
```

Preview the production build:

```bash
npm run preview
```

## Usage Guide

### 1. **Upload Data**

- Click "Choose File" and select a `.jsonl` file with your evaluation results
- The system will automatically parse and group the data

### 2. **Evaluate Responses**

- Review each model response against the expected answer
- Click the appropriate category button (Direct, Inferable, Missing, Hallucination)
- Your evaluations are saved automatically

### 3. **Use Dashboard Analytics**

- Navigate to the Dashboard tab for comprehensive analytics
- View top performers and category distributions
- Analyze text length patterns and conciseness metrics
- Compare models and embedding providers

### 4. **Filter and Sort**

- Use dropdown filters to focus on specific models or providers
- Click column headers to sort by different metrics
- Toggle between infinite scroll and "Show All" modes

### 5. **Export Progress**

- Click "Export Evaluations" to save your progress
- The exported file includes all scores and analytics
- Import the file later to resume evaluation

## Sample Data

Sample data files are included in the `static/` directory:

- `sample-data.jsonl`: Basic example data for testing
- `vizwiz-data.jsonl`: VizWiz dataset examples

## Architecture

### Components

#### Main Page (`src/routes/+page.svelte`)

- File upload and parsing
- State management and filtering
- Data grouping and organization
- Export/import functionality

#### Dashboard (`src/lib/components/Dashboard.svelte`)

- Performance analytics and metrics
- Category analysis and visualization
- Text length statistics
- Top performers identification

#### Results Table (`src/lib/components/ResultsTable.svelte`)

- Main data table with sorting
- Infinite scroll implementation
- Responsive table layout
- Evaluation controls

#### Result Row (`src/lib/components/ResultRow.svelte`)

- Individual result display
- Image handling with lazy loading
- Scoring buttons and indicators
- Similarity and conciseness visualization

#### Image Modal (`src/lib/components/ImageModal.svelte`)

- Full-screen image viewing
- Navigation between images
- Responsive modal design

## Technology Stack

- **Framework**: SvelteKit 2.0
- **Language**: TypeScript
- **Styling**: CSS (component-scoped)
- **Build Tool**: Vite
- **Package Manager**: npm
- **Icons**: Unicode emojis for cross-platform compatibility

## Performance Features

- **Lazy Loading**: Images load only when needed
- **Infinite Scroll**: Efficient handling of large datasets
- **Reactive Updates**: Real-time filtering and sorting
- **Memory Management**: Optimized data structures
- **Caching**: Evaluation progress persistence

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
