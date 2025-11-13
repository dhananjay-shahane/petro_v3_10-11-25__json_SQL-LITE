export async function parseResponse<T = any>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type");
  
  if (contentType && contentType.includes("application/json")) {
    return await response.json();
  } else {
    const text = await response.text();
    const errorMessage = text.length > 200 ? text.substring(0, 200) + "..." : text;
    throw new Error(`Server returned non-JSON response: ${errorMessage}`);
  }
}

export async function handleApiError(response: Response): Promise<never> {
  const contentType = response.headers.get("content-type");
  
  if (contentType && contentType.includes("application/json")) {
    const errorData = await response.json();
    throw new Error(errorData.error || `API Error: ${response.status} ${response.statusText}`);
  } else {
    const text = await response.text();
    const errorMessage = text.length > 200 ? text.substring(0, 200) + "..." : text;
    throw new Error(`Server Error (${response.status}): ${errorMessage}`);
  }
}
