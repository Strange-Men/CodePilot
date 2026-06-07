export function validateGitHubRepositoryUrl(value: string): string | null {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return "Enter a valid GitHub repository URL.";
  }

  const pathParts = url.pathname.split("/").filter(Boolean);
  if (
    url.protocol !== "https:" ||
    url.hostname.toLowerCase() !== "github.com" ||
    pathParts.length !== 2 ||
    Boolean(url.search) ||
    Boolean(url.hash)
  ) {
    return "Use an HTTPS GitHub repository URL such as https://github.com/owner/repository.";
  }
  return null;
}
