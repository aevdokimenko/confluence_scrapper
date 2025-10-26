# Confluence Web Scraper

A Python web scraper that uses the Confluence REST API to extract full page content from a Confluence site and convert it to Markdown format.

## Features

- Authenticates using session cookies
- Retrieves all pages from a specified Confluence space
- Converts HTML content to clean Markdown format
- Preserves page hierarchy and metadata
- Implements random delays to simulate human interaction
- Processes pages in non-sequential order to avoid detection
- Saves content locally with organized file structure

## Requirements

- Python 3.7+
- Valid Confluence session cookie
- Access to the Confluence site you want to scrape

## Installation

1. Clone or download this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. **Get your session cookie:**
   - Open your browser and navigate to your Confluence site
   - Log in to Confluence
   - Open Developer Tools (F12)
   - Go to the Application/Storage tab
   - Find the `JSESSIONID` cookie value
   - Copy this value

2. **Run the scraper:**

```bash
python scraper.py
```

3. **Follow the prompts:**
   - Enter your session cookie when prompted
   - Enter the space key (e.g., "ARR", "DEV", etc.)

4. **Results:**
   - All scraped content will be saved in the `scraped_content` directory
   - Each page is saved as a separate Markdown file with metadata
   - A hierarchy file shows the structure of all pages in the space

## Output Structure

```
scraped_content/
├── SPACENAME_hierarchy.md          # Page hierarchy overview
├── 1234567_Page_Title.md           # Individual page files
├── 2345678_Another_Page.md
└── ...
```

Each page file includes:
- YAML front matter with page metadata (ID, title, type, status, position)
- Clean Markdown content converted from HTML

## Configuration

You can modify the scraper behavior by editing these parameters in `scraper.py`:

- `min_seconds` and `max_seconds` in `random_delay()`: Adjust delay between requests
- `limit` in `get_space_pages()`: Number of pages to fetch per request
- `output_dir`: Directory where content is saved

## Important Notes

- **Respect Rate Limits:** The scraper includes random delays to avoid overwhelming the server
- **Session Cookies Expire:** You may need to refresh your session cookie periodically
- **Large Spaces:** For spaces with many pages, the scraping process may take considerable time
- **Content Format:** Some complex Confluence macros may not convert perfectly to Markdown

## Troubleshooting

**Authentication Issues:**
- Ensure your session cookie is valid and not expired
- Check that you have access to the specified space

**Network Issues:**
- The scraper will log errors for failed requests
- Check your internet connection and Confluence server availability

**Permission Issues:**
- Verify you have read access to all pages in the space
- Some pages may be restricted and won't be accessible

## Legal and Ethical Considerations

- Only scrape content you have legitimate access to
- Respect the terms of service of your Confluence instance
- Be mindful of confidential or sensitive information
- Use reasonable delays to avoid impacting server performance

## License

This project is provided as-is for educational and legitimate business purposes.