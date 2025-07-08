# Vision RAG Evaluation Viewer

A dynamic SvelteKit web application for visualizing and comparing Vision RAG (Retrieval Augmented Generation) evaluation results. This tool allows users to upload JSONL files containing evaluation data and provides an interactive interface for filtering and comparing model performance with and without context.

## Features

- **File Upload**: Upload `.jsonl` files containing evaluation results
- **Dynamic Filtering**: Filter results by:
  - Model name
  - Context type (with/without context)
  - Embedding provider
- **Side-by-Side Comparison**: Compare responses with and without context for each query
- **Visual Context Display**: View query images and similar context images
- **Responsive Design**: Works on desktop and mobile devices
- **Error Handling**: Display processing errors and missing data gracefully

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
  "processing_time": number
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

## Usage

1. **Upload Data**: Click "Choose File" and select a `.jsonl` file containing your evaluation results
2. **Filter Results**: Use the dropdown filters to narrow down results by:
   - Model (all models, or specific model names)
   - Context (all, with context only, without context only)
   - Embedding Provider (all providers, or specific providers)
3. **Review Results**: Examine the table showing:
   - Query images
   - Question details and expected answers
   - Model information
   - Context images (if available)
   - Side-by-side comparison of responses with and without context
   - Processing times and error information

## Sample Data

A sample data file is included at `static/sample-data.jsonl` for testing purposes. This file contains example evaluations across different models and embedding providers.

## Architecture

The application consists of three main Svelte components:

### Main Page (`src/routes/+page.svelte`)

- Handles file upload and parsing
- Manages application state and filtering
- Groups data by validation_id, model_name, and embedding_provider
- Provides reactive filtering based on user selections

### Results Table (`src/lib/components/ResultsTable.svelte`)

- Renders the main data table structure
- Handles responsive table layout
- Shows "no results" state when filtered data is empty

### Result Row (`src/lib/components/ResultRow.svelte`)

- Displays individual result rows
- Handles image display with lazy loading
- Formats processing times and truncates long responses
- Shows error states with appropriate styling
- Provides visual indicators for context vs. no-context responses

## Technology Stack

- **Framework**: SvelteKit 2.0
- **Language**: TypeScript
- **Styling**: CSS (component-scoped)
- **Build Tool**: Vite
- **Package Manager**: npm

## Browser Support

The application supports all modern browsers with ES2020+ support. Images are loaded with lazy loading for optimal performance.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the MIT License.
