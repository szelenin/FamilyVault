
// this file is generated — do not edit it


declare module "svelte/elements" {
	export interface HTMLAttributes<T> {
		'data-sveltekit-keepfocus'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-noscroll'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-preload-code'?:
			| true
			| ''
			| 'eager'
			| 'viewport'
			| 'hover'
			| 'tap'
			| 'off'
			| undefined
			| null;
		'data-sveltekit-preload-data'?: true | '' | 'hover' | 'tap' | 'off' | undefined | null;
		'data-sveltekit-reload'?: true | '' | 'off' | undefined | null;
		'data-sveltekit-replacestate'?: true | '' | 'off' | undefined | null;
	}
}

export {};


declare module "$app/types" {
	type MatcherParam<M> = M extends (param : string) => param is (infer U extends string) ? U : string;

	export interface AppTypes {
		RouteId(): "/" | "/api" | "/api/favorite" | "/api/favorite/[assetId]" | "/api/project" | "/api/project/[id]" | "/api/project/[id]/select" | "/api/thumbnail" | "/api/thumbnail/[assetId]" | "/project" | "/project/[id]" | "/project/[id]/scene" | "/project/[id]/scene/[sceneId]";
		RouteParams(): {
			"/api/favorite/[assetId]": { assetId: string };
			"/api/project/[id]": { id: string };
			"/api/project/[id]/select": { id: string };
			"/api/thumbnail/[assetId]": { assetId: string };
			"/project/[id]": { id: string };
			"/project/[id]/scene": { id: string };
			"/project/[id]/scene/[sceneId]": { id: string; sceneId: string }
		};
		LayoutParams(): {
			"/": { assetId?: string; id?: string; sceneId?: string };
			"/api": { assetId?: string; id?: string };
			"/api/favorite": { assetId?: string };
			"/api/favorite/[assetId]": { assetId: string };
			"/api/project": { id?: string };
			"/api/project/[id]": { id: string };
			"/api/project/[id]/select": { id: string };
			"/api/thumbnail": { assetId?: string };
			"/api/thumbnail/[assetId]": { assetId: string };
			"/project": { id?: string; sceneId?: string };
			"/project/[id]": { id: string; sceneId?: string };
			"/project/[id]/scene": { id: string; sceneId?: string };
			"/project/[id]/scene/[sceneId]": { id: string; sceneId: string }
		};
		Pathname(): "/" | `/api/favorite/${string}` & {} | `/api/project/${string}` & {} | `/api/project/${string}/select` & {} | `/api/thumbnail/${string}` & {} | `/project/${string}` & {} | `/project/${string}/scene/${string}` & {};
		ResolvedPathname(): `${"" | `/${string}`}${ReturnType<AppTypes['Pathname']>}`;
		Asset(): "/manifest.json" | string & {};
	}
}