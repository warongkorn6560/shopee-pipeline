import "server-only";
import { cache } from "react";
import { FLOWS } from "./flows";
import { githubConfigured } from "./github";
import { elevenLabs, gatewayCredits, telegramBot } from "./health";
import { storeConfigured } from "./store";
import { getProducts, getRunsFor, getSecrets, getStories, getVariables, getVideos, getWorkflows } from "./data";
import type { StatusContext } from "./status";

/** Everything the overview needs, fetched in parallel once per request. */
export const loadContext = cache(async (): Promise<StatusContext & { errors: string[] }> => {
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
  };
});
