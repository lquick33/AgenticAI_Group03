"""
Helper utilities for the project.
"""

import os


# Check if we have the required API key
def check_api_setup():
    """
    Check if the Google API key is properly configured.

    Returns:
        True if the Google API key is properly configured, False otherwise
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        print("✅ Google API key found!")
        print(f"Key ends with:****{api_key[-2:]}")
        return True
    else:
        print("❌ Google API key not found!")
        print("Please set your GOOGLE_API_KEY environment variable.")
        print("\nTo get a free API key:")
        print("1. Go to https://makersuite.google.com/app/apikey")
        print("2. Create a new API key")
        print("3. Set it as an environment variable: export GOOGLE_API_KEY='your-key-here'")
        print("4. Or create a .env file in your project root with: GOOGLE_API_KEY=your-key-here")
        return False


# Example usage and testing
if __name__ == "__main__":
    check_api_setup()