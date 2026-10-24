import "server-only";
import { cache } from "react";
import { FLOWS } from "./flows";
import { githubConfigured } from "./github";
import { elevenLabs, gatewayCredits, telegramBot } from "./health";
import { storeConfigured } from "./store";
import { getProducts, getRunsFor, getSecrets, getStories, getVariables, getVideos, getWorkflows } from "./data";
import type { StatusContext } from "./status";
import type { Video } from "./store";

/** Month-to-date Claude spend (Bangkok calendar month), summed from the per-video cost reports. */
export function claudeThisMonth(videos: Video[]): ClaudeMonth {
  const month = (d: Date) => new Date(d.getTime() + 7 * 3_600_000).toISOString().slice(0, 7);
  const now = month(new Date());
  const mine = videos.filter((v) => month(new Date(v.createdAt)) === now);
  const priced = mine.filter((v) => v.cost);
  return { usd: priced.reduce((t, v) => t + v.cost!.claudeUsd, 0), videos: mine.length, withCost: priced.length };
}

/** Everything the overview needs, fetched in parallel once per request. */
type ClaudeMonth = { usd: number; videos: number; withCost: number };

export const loadContext = cache(async (): Promise<StatusContext & { errors: string[]; claudeMonth: ClaudeMonth | null }> => {
  const github = githubConfigured();
  const primaries = FLOWS.map((f) => f.workflows.find((w) => w.primary)!.file);
  const hasStore = storeConfigured();
  const [workflows, vars, secrets, eleven, gateway, telegram, products, stories, videos, ...runs] = await Promise.all([
    github ? getWorkflows() : null,
    github ? getVariables() : null,
    github ? getSecrets() : null,
    elevenLabs(),
    gatewayCredits(),
    telegramBot(),
    hasStore ? getProducts() : null,
    hasStore ? getStories() : null,
    hasStore ? getVideos() : null,
    ...primaries.map((f) => (github ? getRunsFor(f) : null)),
  ]);
  const errors: string[] = [];
  for (const [label, s] of [["GitHub", workflows], ["คลังข้อมูล", products]] as const) {
    if (s && !s.ok) errors.push(`${label}: ${s.error}`);
  }
  const latest: StatusContext["latest"] = {};
  primaries.forEach((f, i) => {
    const r = runs[i];
    latest[f] = r && r.ok ? r.value[0] : undefined;
  });
  return {
    github,
    workflows: workflows?.ok ? workflows.value : null,
    vars: vars?.ok ? vars.value : null,
    secrets: secrets?.ok ? secrets.value : null,
    eleven,
    gateway,
    telegram,
    readyProducts: products?.ok ? products.value.filter((p) => p.status === "Ready").length : null,
    readyStories: stories?.ok ? stories.value.filter((s) => s.status === "Ready").length : null,
    pendingReviews: videos?.ok ? videos.value.filter((v) => v.status === "review").length : null,
    latest,
    errors,
    claudeMonth: videos?.ok ? claudeThisMonth(videos.value) : null,
  };
});
