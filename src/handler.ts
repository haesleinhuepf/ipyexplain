import { URLExt } from '@jupyterlab/coreutils';
import { ServerConnection } from '@jupyterlab/services';

/**
 * Call the API extension
 */
export async function requestAPI<T>(
  endPoint = '',
  init: RequestInit = {}
): Promise<T> {
  const settings = ServerConnection.makeSettings();
  const requestUrl = URLExt.join(
    settings.baseUrl,
    'ipyexplain',
    endPoint
  );

  let response: Response;
  try {
    response = await ServerConnection.makeRequest(requestUrl, init, settings);
  } catch (error) {
    throw new ServerConnection.NetworkError(error as TypeError);
  }

  let data: T;
  try {
    data = await response.json();
  } catch (error) {
    throw new Error(`Not a JSON response: ${response.status} ${response.statusText}`);
  }

  if (!response.ok) {
    throw new ServerConnection.ResponseError(response, (data as any).message || response.statusText);
  }

  return data;
}
