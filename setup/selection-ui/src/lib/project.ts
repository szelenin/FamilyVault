import fs from "fs";
import path from "path";

const STORIES_DIR = process.env.STORIES_DIR || "/Volumes/HomeRAID/stories";

export interface Scene {
  id: string;
  label: string;
  time_range: string[];
  photo_count: number;
  video_count: number;
  cities: string[];
  people: string[];
  asset_ids: string[];
}

export interface Project {
  id: string;
  title: string;
  state: string;
  discovery: {
    scenes: Scene[];
    total_candidates: number;
  };
  timeline: any[];
  deselected_ids?: string[];
  assembly_config?: any;
}

export function loadProject(projectId: string): Project {
  const filePath = path.join(STORIES_DIR, projectId, "project.json");
  const data = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(data);
}

export function saveDeselectedIds(projectId: string, deselectedIds: string[]): void {
  const filePath = path.join(STORIES_DIR, projectId, "project.json");
  const project = JSON.parse(fs.readFileSync(filePath, "utf-8"));
  project.deselected_ids = deselectedIds;
  fs.writeFileSync(filePath, JSON.stringify(project, null, 2));
}

export function archiveProject(projectId: string): void {
  const src = path.join(STORIES_DIR, projectId);
  const archiveDir = path.join(STORIES_DIR, "_archive");
  if (!fs.existsSync(archiveDir)) fs.mkdirSync(archiveDir, { recursive: true });
  const dst = path.join(archiveDir, projectId);
  fs.renameSync(src, dst);
}

export function listProjects(): string[] {
  try {
    return fs.readdirSync(STORIES_DIR)
      .filter(d => {
        if (d.startsWith("_")) return false;
        const fp = path.join(STORIES_DIR, d, "project.json");
        return fs.existsSync(fp);
      })
      .sort()
      .reverse();
  } catch { return []; }
}
