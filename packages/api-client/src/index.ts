import createFetchClient, { type Client } from "openapi-fetch";
import type { paths } from "./schema.js";

export type { paths } from "./schema.js";
export type ApiClient = Client<paths>;

export interface ClientOptions {
  baseUrl?: string;
  getToken?: () => Promise<string | null> | string | null;
}

/**
 * Create a strongly-typed API client for the Studio backend.
 *
 * @param baseUrl Base URL of the API (e.g. "http://localhost:8000")
 * @param getToken Async or sync function returning a Bearer token or null
 */
export function createClient(
  baseUrl: string = "http://localhost:8000",
  getToken?: () => Promise<string | null> | string | null
): ApiClient {
  const client = createFetchClient<paths>({
    baseUrl,
  });

  if (getToken) {
    client.use({
      async onRequest({ request }) {
        const token = await getToken();
        if (token) {
          request.headers.set("Authorization", `Bearer ${token}`);
        }
        return request;
      },
    });
  }

  return client;
}
