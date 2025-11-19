"""
URL fetcher tool for fetching and extracting content from web pages.
"""

import re
from typing import Union
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field


class UrlFetcherInput(BaseModel):
    """Input schema for the URL fetcher tool."""
    url: str = Field(description="The URL to fetch (must be a valid HTTP/HTTPS URL)")
    extract_text: bool = Field(
        default=True,
        description="Whether to extract text from HTML (default: True). Set to False to get raw HTML."
    )


class UrlFetcherTool(BaseTool):
    """
    A tool for fetching content from URLs with proper redirect handling.
    
    This tool can handle HTTP redirects, extract text from HTML pages, and
    follow meta refresh and JavaScript redirects. It's designed to work around
    common issues with URL fetching in web scraping scenarios.
    """
    
    def __init__(self):
        super().__init__(
            name="fetch_url",
            description="""
            Fetch content from a URL using HTTP requests. This tool AUTOMATICALLY handles redirects
            and returns the actual content from the final destination URL.
            
            CRITICAL: Use this tool instead of fetch_docs when:
            - fetch_docs returns "Redirecting..." 
            - You need to fetch specific documentation pages
            - You encounter any redirect-related issues
            
            This tool follows HTTP redirects automatically and extracts readable text from HTML pages.
            It is the preferred tool for fetching LangGraph and LangChain documentation pages.
            """
        )
    
    def _run(
        self, 
        url: str, 
        extract_text: bool = True
    ) -> str:
        """
        Fetch content from a URL using the requests library.
        This tool can handle redirects properly and extract text from HTML.
        
        Args:
            url: The URL to fetch
            extract_text: If True, extract text from HTML. If False, return raw HTML.
        
        Returns:
            The content from the URL, or an error message if the fetch fails.
        """
        return self._fetch_with_redirects(url, extract_text, _redirect_depth=0)
    
    def _fetch_with_redirects(
        self,
        url: str,
        extract_text: bool = True,
        _redirect_depth: int = 0
    ) -> str:
        """
        Internal method to fetch content with redirect handling.
        
        Args:
            url: The URL to fetch
            extract_text: If True, extract text from HTML. If False, return raw HTML.
            _redirect_depth: Internal parameter to prevent infinite redirect loops (max 5)
        
        Returns:
            The content from the URL, or an error message if the fetch fails.
        """
        # Prevent infinite redirect loops
        if _redirect_depth > 5:
            return f"Error: Too many redirects (max 5) for URL: {url}"
        
        try:
            # Create a session to handle cookies and maintain connection
            session = requests.Session()
            
            # Use realistic browser headers to avoid being blocked
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            }
            
            # Follow redirects automatically (this is the default, but being explicit)
            response = session.get(
                url, 
                headers=headers, 
                timeout=30, 
                allow_redirects=True,
                verify=True,  # Verify SSL certificates
                stream=False  # Don't stream, get full response
            )
            
            # Check if we got redirected
            if response.history:
                redirect_count = len(response.history)
                final_url = response.url
                # Don't print in the tool output, just track it
            
            response.raise_for_status()  # Raise an exception for bad status codes
            
            # Get content type
            content_type = response.headers.get('Content-Type', '').lower()
            
            # Check if response is actually HTML content
            if 'text/html' in content_type or response.text.strip().startswith('<!'):
                # Check for meta refresh or JavaScript redirects in the HTML
                html_text = response.text
                soup = BeautifulSoup(html_text, 'html.parser')
                
                # Check for meta refresh redirects
                meta_refresh = soup.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'refresh'})
                if meta_refresh:
                    content = meta_refresh.get('content', '')
                    # Extract URL from meta refresh (format: "0;url=http://...")
                    if 'url=' in content.lower():
                        redirect_url = content.split('url=')[-1].strip()
                        # Recursively follow the redirect (with depth tracking)
                        return self._fetch_with_redirects(redirect_url, extract_text, _redirect_depth + 1)
                
                # Check if the page content is just "Redirecting..." - might be a JS redirect
                body_text = soup.get_text().strip() if soup.find('body') else ''
                if body_text.lower() in ['redirecting...', 'redirecting'] and len(body_text) < 100:
                    # Look for JavaScript redirects
                    scripts = soup.find_all('script')
                    for script in scripts:
                        script_text = script.string or ''
                        # Look for common redirect patterns
                        if 'window.location' in script_text or 'location.href' in script_text:
                            # Try to extract URL from JavaScript
                            patterns = [
                                r"window\.location\s*=\s*['\"]([^'\"]+)['\"]",
                                r"location\.href\s*=\s*['\"]([^'\"]+)['\"]",
                                r"window\.location\.replace\(['\"]([^'\"]+)['\"]\)",
                            ]
                            for pattern in patterns:
                                match = re.search(pattern, script_text)
                                if match:
                                    redirect_url = match.group(1)
                                    # Handle relative URLs
                                    if redirect_url.startswith('/'):
                                        redirect_url = urljoin(url, redirect_url)
                                    elif not redirect_url.startswith('http'):
                                        redirect_url = urljoin(url, redirect_url)
                                    # Recursively follow the redirect (with depth tracking)
                                    return self._fetch_with_redirects(redirect_url, extract_text, _redirect_depth + 1)
                
                # If we want to extract text from HTML
                if extract_text:
                    # Try multiple strategies to find main content FIRST
                    # (before removing elements, so structure is preserved)
                    main_content = None
                    # Strategy 1: Look for semantic HTML5 elements
                    main_content = soup.find('main') or soup.find('article')
                    
                    # Strategy 2: Look for common content class names (including MkDocs patterns)
                    if not main_content:
                        for class_name in ['content', 'main-content', 'post-content', 'article-content', 'doc-content', 
                                         'markdown', 'prose', 'md-content', 'md-typeset', 'md-main__inner', 
                                         'md-content__inner', 'md-content__inner-wrapper']:
                            # Try finding by class (handles both single class and multiple classes)
                            main_content = soup.find('div', class_=lambda x: x and class_name in ' '.join(x) if isinstance(x, list) else class_name in str(x))
                            if main_content:
                                break
                    
                    # Strategy 3: Look for divs with id containing 'content' or common doc patterns
                    if not main_content:
                        main_content = soup.find('div', id=lambda x: x and ('content' in x.lower() or 'main' in x.lower() or 'doc' in x.lower()))
                    
                    # Strategy 4: Look for common documentation site patterns (MkDocs, Sphinx, etc.)
                    if not main_content:
                        # Try finding by data attributes or specific patterns
                        main_content = soup.find('div', attrs={'role': 'main'}) or soup.find('div', attrs={'role': 'article'})
                    
                    # Strategy 5: Look for the largest div with text content (fallback heuristic)
                    if not main_content:
                        # Find all divs and pick the one with the most text
                        all_divs = soup.find_all('div')
                        if all_divs:
                            main_content = max(all_divs, key=lambda d: len(d.get_text(strip=True)))
                            # Only use if it has substantial content (more than just a few words)
                            if len(main_content.get_text(strip=True)) < 100:
                                main_content = None
                    
                    # Strategy 6: Use body if nothing else found
                    if not main_content:
                        main_content = soup.find('body')
                    
                    if main_content:
                        # Now remove script, style, and other non-content elements from the main content
                        # Work directly with main_content (decompose modifies in place)
                        for element in main_content.find_all(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
                            element.decompose()
                        text = main_content.get_text()
                    else:
                        # Fallback: remove unwanted elements from entire document
                        for element in soup.find_all(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
                            element.decompose()
                        text = soup.get_text()
                    
                    # Clean up whitespace
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = '\n'.join(chunk for chunk in chunks if chunk)
                    
                    # Add metadata
                    title = soup.find('title')
                    if title:
                        title_text = title.get_text().strip()
                        if title_text and title_text.lower() not in ['redirecting...', 'redirecting']:
                            text = f"Title: {title_text}\n\n{text}"
                    
                    # Add URL info
                    if response.history:
                        text = f"URL: {url}\nFinal URL after redirects: {response.url}\n\n{text}"
                    
                    return text
                else:
                    # Return raw HTML
                    return response.text
            else:
                # Return raw content for non-HTML
                return response.text
                
        except requests.exceptions.TooManyRedirects as e:
            return f"Error: Too many redirects for URL: {url}. Last URL: {e.response.url if hasattr(e, 'response') else 'unknown'}"
        except requests.exceptions.Timeout:
            return f"Error: Request timed out for URL: {url}"
        except requests.exceptions.HTTPError as e:
            return f"Error: HTTP {e.response.status_code} for URL: {url}. Response: {e.response.text[:200]}"
        except requests.exceptions.RequestException as e:
            return f"Error fetching URL {url}: {str(e)}"
        except Exception as e:
            return f"Error processing URL {url}: {type(e).__name__}: {str(e)}"
    
    def to_langchain_tool(self) -> StructuredTool:
        """Convert to LangChain StructuredTool."""
        # Create a wrapper function that properly calls the method
        def fetch_url_wrapper(url: str, extract_text: bool = True) -> str:
            """Wrapper function for StructuredTool."""
            return self._run(url=url, extract_text=extract_text)
        
        return StructuredTool(
            name=self.name,
            description=self.description,
            func=fetch_url_wrapper,
            args_schema=UrlFetcherInput
        )


# Example usage and testing
if __name__ == "__main__":
    fetcher = UrlFetcherTool()
    
    # Test cases
    test_urls = [
        "https://www.example.com",
        "https://langchain-ai.github.io/langgraph/index/",
    ]
    
    for url in test_urls:
        print(f"\n{'='*80}")
        print(f"Fetching: {url}")
        print(f"{'='*80}")
        result = fetcher._run(url, extract_text=True)
        print(result[:500] + "..." if len(result) > 500 else result)
        print()