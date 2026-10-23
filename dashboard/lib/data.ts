import "server-only";
import { cache } from "react";
import { VARIABLES } from "./flows";
import * as gh from "./github";
import * as store from "./store";

export type Settled<T> = { ok: true; value: T } | { ok: false; error: string };

export async function settle<T>(p: Promise<T>): Promise<Settled<T>> {
  try {
    return { ok: true, value: await p };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

// Deduplicated per request: several panels on one page share these reads.
export const getWorkflows = cache(() => settle(gh.listWorkflows()));
export const getVariables = cache(() => settle(gh.listVariables()));
export const getSecrets = cache(() => settle(gh.listSecretNames()));
export const getRecentRuns = cache(() => settle(gh.listRuns(15)));
export const getRunsFor = cache((file: string) => settle(gh.listRunsFor(file, 5)));
export const getProducts = cache(() => settle(store.list("products")));
export const getStories = cache(() => settle(store.list("stories")));
export const getVideos = cache(() => settle(store.list("videos")));

export function effective(vars: Record<string, { value: string }> | null, name: string): string {
  const def = VARIABLES.find((v) => v.name === name);
  return vars?.[name]?.value || def?.workflowDefault || "";
}
