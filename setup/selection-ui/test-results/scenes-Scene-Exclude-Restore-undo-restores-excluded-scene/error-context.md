# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: scenes.test.ts >> Scene Exclude & Restore >> undo restores excluded scene
- Location: tests/e2e/scenes.test.ts:54:3

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: 'Undo' })

```

# Page snapshot

```yaml
- generic [ref=e2]:
  - banner [ref=e3]:
    - link "Story Engine" [ref=e4] [cursor=pointer]:
      - /url: /
  - main [ref=e5]:
    - generic [ref=e6]:
      - link "← Projects" [ref=e7] [cursor=pointer]:
        - /url: /
      - heading "Miami Trip - Last Visit" [level=1] [ref=e8]
      - paragraph [ref=e9]: 501/501 selected · 42 scenes
    - generic [ref=e10]:
      - generic [ref=e11]:
        - link "Scene 1 2026-03-26 21:41 · 1 photos, 0 videos 1/1" [ref=e12] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-000
          - generic [ref=e13]:
            - generic [ref=e14]: Scene 1
            - generic [ref=e15]: 2026-03-26 21:41 ·
            - generic [ref=e16]: 1 photos, 0 videos
          - generic [ref=e18]: 1/1
        - button [active] [ref=e19]:
          - img [ref=e20]
      - generic [ref=e23]:
        - link "Scene 2 2026-03-27 10:19 · Wesley Chapel 1 photos, 0 videos 1/1" [ref=e24] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-001
          - generic [ref=e25]:
            - generic [ref=e26]: Scene 2
            - generic [ref=e27]: 2026-03-27 10:19 · Wesley Chapel
            - generic [ref=e28]: 1 photos, 0 videos
          - generic [ref=e30]: 1/1
        - button [ref=e31]:
          - img [ref=e32]
      - generic [ref=e35]:
        - link "Scene 3 2026-03-27 14:08 · 1 photos, 0 videos 1/1" [ref=e36] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-002
          - generic [ref=e37]:
            - generic [ref=e38]: Scene 3
            - generic [ref=e39]: 2026-03-27 14:08 ·
            - generic [ref=e40]: 1 photos, 0 videos
          - generic [ref=e42]: 1/1
        - button [ref=e43]:
          - img [ref=e44]
      - generic [ref=e47]:
        - link "Scene 4 2026-03-27 14:52 · 1 photos, 0 videos 1/1" [ref=e48] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-003
          - generic [ref=e49]:
            - generic [ref=e50]: Scene 4
            - generic [ref=e51]: 2026-03-27 14:52 ·
            - generic [ref=e52]: 1 photos, 0 videos
          - generic [ref=e54]: 1/1
        - button [ref=e55]:
          - img [ref=e56]
      - generic [ref=e59]:
        - link "Scene 5 2026-03-27 15:53 · 3 photos, 0 videos 3/3" [ref=e60] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-004
          - generic [ref=e61]:
            - generic [ref=e62]: Scene 5
            - generic [ref=e63]: 2026-03-27 15:53 ·
            - generic [ref=e64]: 3 photos, 0 videos
          - generic [ref=e66]: 3/3
        - button [ref=e67]:
          - img [ref=e68]
      - generic [ref=e71]:
        - link "Scene 6 2026-03-27 17:02 · 3 photos, 0 videos 3/3" [ref=e72] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-005
          - generic [ref=e73]:
            - generic [ref=e74]: Scene 6
            - generic [ref=e75]: 2026-03-27 17:02 ·
            - generic [ref=e76]: 3 photos, 0 videos
          - generic [ref=e78]: 3/3
        - button [ref=e79]:
          - img [ref=e80]
      - generic [ref=e83]:
        - link "Scene 7 2026-03-27 18:01 · 1 photos, 0 videos 1/1" [ref=e84] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-006
          - generic [ref=e85]:
            - generic [ref=e86]: Scene 7
            - generic [ref=e87]: 2026-03-27 18:01 ·
            - generic [ref=e88]: 1 photos, 0 videos
          - generic [ref=e90]: 1/1
        - button [ref=e91]:
          - img [ref=e92]
      - generic [ref=e95]:
        - link "Scene 8 2026-03-27 20:03 · 1 photos, 0 videos 1/1" [ref=e96] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-007
          - generic [ref=e97]:
            - generic [ref=e98]: Scene 8
            - generic [ref=e99]: 2026-03-27 20:03 ·
            - generic [ref=e100]: 1 photos, 0 videos
          - generic [ref=e102]: 1/1
        - button [ref=e103]:
          - img [ref=e104]
      - generic [ref=e107]:
        - link "Scene 9 2026-03-27 20:40 · 10 photos, 0 videos 10/10" [ref=e108] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-008
          - generic [ref=e109]:
            - generic [ref=e110]: Scene 9
            - generic [ref=e111]: 2026-03-27 20:40 ·
            - generic [ref=e112]: 10 photos, 0 videos
          - generic [ref=e114]: 10/10
        - button [ref=e115]:
          - img [ref=e116]
      - generic [ref=e119]:
        - link "Scene 10 2026-03-27 22:32 · 4 photos, 0 videos 4/4" [ref=e120] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-009
          - generic [ref=e121]:
            - generic [ref=e122]: Scene 10
            - generic [ref=e123]: 2026-03-27 22:32 ·
            - generic [ref=e124]: 4 photos, 0 videos
          - generic [ref=e126]: 4/4
        - button [ref=e127]:
          - img [ref=e128]
      - generic [ref=e131]:
        - link "Scene 11 2026-03-28 09:33 · 5 photos, 0 videos 5/5" [ref=e132] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-010
          - generic [ref=e133]:
            - generic [ref=e134]: Scene 11
            - generic [ref=e135]: 2026-03-28 09:33 ·
            - generic [ref=e136]: 5 photos, 0 videos
          - generic [ref=e138]: 5/5
        - button [ref=e139]:
          - img [ref=e140]
      - generic [ref=e143]:
        - link "Scene 12 2026-03-28 15:58 · 3 photos, 10 videos 13/13" [ref=e144] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-011
          - generic [ref=e145]:
            - generic [ref=e146]: Scene 12
            - generic [ref=e147]: 2026-03-28 15:58 ·
            - generic [ref=e148]: 3 photos, 10 videos
          - generic [ref=e150]: 13/13
        - button [ref=e151]:
          - img [ref=e152]
      - generic [ref=e155]:
        - link "Scene 13 2026-03-28 17:19 · 45 photos, 12 videos 57/57" [ref=e156] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-012
          - generic [ref=e157]:
            - generic [ref=e158]: Scene 13
            - generic [ref=e159]: 2026-03-28 17:19 ·
            - generic [ref=e160]: 45 photos, 12 videos
          - generic [ref=e162]: 57/57
        - button [ref=e163]:
          - img [ref=e164]
      - generic [ref=e167]:
        - link "Scene 14 2026-03-28 20:51 · 0 photos, 1 videos 1/1" [ref=e168] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-013
          - generic [ref=e169]:
            - generic [ref=e170]: Scene 14
            - generic [ref=e171]: 2026-03-28 20:51 ·
            - generic [ref=e172]: 0 photos, 1 videos
          - generic [ref=e174]: 1/1
        - button [ref=e175]:
          - img [ref=e176]
      - generic [ref=e179]:
        - link "Scene 15 2026-03-29 11:25 · 1 photos, 0 videos 1/1" [ref=e180] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-014
          - generic [ref=e181]:
            - generic [ref=e182]: Scene 15
            - generic [ref=e183]: 2026-03-29 11:25 ·
            - generic [ref=e184]: 1 photos, 0 videos
          - generic [ref=e186]: 1/1
        - button [ref=e187]:
          - img [ref=e188]
      - generic [ref=e191]:
        - link "Scene 16 2026-03-29 20:21 · Miami Beach 2 photos, 0 videos 2/2" [ref=e192] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-015
          - generic [ref=e193]:
            - generic [ref=e194]: Scene 16
            - generic [ref=e195]: 2026-03-29 20:21 · Miami Beach
            - generic [ref=e196]: 2 photos, 0 videos
          - generic [ref=e198]: 2/2
        - button [ref=e199]:
          - img [ref=e200]
      - generic [ref=e203]:
        - link "Scene 17 2026-03-29 21:46 · 1 photos, 0 videos 1/1" [ref=e204] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-016
          - generic [ref=e205]:
            - generic [ref=e206]: Scene 17
            - generic [ref=e207]: 2026-03-29 21:46 ·
            - generic [ref=e208]: 1 photos, 0 videos
          - generic [ref=e210]: 1/1
        - button [ref=e211]:
          - img [ref=e212]
      - generic [ref=e215]:
        - link "Scene 18 2026-03-29 22:41 · Miami Beach 1 photos, 0 videos 1/1" [ref=e216] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-017
          - generic [ref=e217]:
            - generic [ref=e218]: Scene 18
            - generic [ref=e219]: 2026-03-29 22:41 · Miami Beach
            - generic [ref=e220]: 1 photos, 0 videos
          - generic [ref=e222]: 1/1
        - button [ref=e223]:
          - img [ref=e224]
      - generic [ref=e227]:
        - link "Scene 19 2026-03-30 08:37 · Miami Beach 3 photos, 0 videos 3/3" [ref=e228] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-018
          - generic [ref=e229]:
            - generic [ref=e230]: Scene 19
            - generic [ref=e231]: 2026-03-30 08:37 · Miami Beach
            - generic [ref=e232]: 3 photos, 0 videos
          - generic [ref=e234]: 3/3
        - button [ref=e235]:
          - img [ref=e236]
      - generic [ref=e239]:
        - link "Scene 20 2026-03-30 11:30 · 9 photos, 0 videos 9/9" [ref=e240] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-019
          - generic [ref=e241]:
            - generic [ref=e242]: Scene 20
            - generic [ref=e243]: 2026-03-30 11:30 ·
            - generic [ref=e244]: 9 photos, 0 videos
          - generic [ref=e246]: 9/9
        - button [ref=e247]:
          - img [ref=e248]
      - generic [ref=e251]:
        - link "Scene 21 2026-03-30 14:01 · 0 photos, 1 videos 1/1" [ref=e252] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-020
          - generic [ref=e253]:
            - generic [ref=e254]: Scene 21
            - generic [ref=e255]: 2026-03-30 14:01 ·
            - generic [ref=e256]: 0 photos, 1 videos
          - generic [ref=e258]: 1/1
        - button [ref=e259]:
          - img [ref=e260]
      - generic [ref=e263]:
        - link "Scene 22 2026-03-30 14:35 · 1 photos, 1 videos 2/2" [ref=e264] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-021
          - generic [ref=e265]:
            - generic [ref=e266]: Scene 22
            - generic [ref=e267]: 2026-03-30 14:35 ·
            - generic [ref=e268]: 1 photos, 1 videos
          - generic [ref=e270]: 2/2
        - button [ref=e271]:
          - img [ref=e272]
      - generic [ref=e275]:
        - link "Scene 23 2026-03-30 17:10 · 1 photos, 0 videos 1/1" [ref=e276] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-022
          - generic [ref=e277]:
            - generic [ref=e278]: Scene 23
            - generic [ref=e279]: 2026-03-30 17:10 ·
            - generic [ref=e280]: 1 photos, 0 videos
          - generic [ref=e282]: 1/1
        - button [ref=e283]:
          - img [ref=e284]
      - generic [ref=e287]:
        - link "Scene 24 2026-03-30 20:02 · Coconut Grove 3 photos, 1 videos 4/4" [ref=e288] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-023
          - generic [ref=e289]:
            - generic [ref=e290]: Scene 24
            - generic [ref=e291]: 2026-03-30 20:02 · Coconut Grove
            - generic [ref=e292]: 3 photos, 1 videos
          - generic [ref=e294]: 4/4
        - button [ref=e295]:
          - img [ref=e296]
      - generic [ref=e299]:
        - link "Scene 25 2026-03-30 22:29 · 0 photos, 1 videos 1/1" [ref=e300] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-024
          - generic [ref=e301]:
            - generic [ref=e302]: Scene 25
            - generic [ref=e303]: 2026-03-30 22:29 ·
            - generic [ref=e304]: 0 photos, 1 videos
          - generic [ref=e306]: 1/1
        - button [ref=e307]:
          - img [ref=e308]
      - generic [ref=e311]:
        - link "Scene 26 2026-03-31 10:46 · 13 photos, 0 videos 13/13" [ref=e312] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-025
          - generic [ref=e313]:
            - generic [ref=e314]: Scene 26
            - generic [ref=e315]: 2026-03-31 10:46 ·
            - generic [ref=e316]: 13 photos, 0 videos
          - generic [ref=e318]: 13/13
        - button [ref=e319]:
          - img [ref=e320]
      - generic [ref=e323]:
        - link "Scene 27 2026-03-31 12:08 · Miami 9 photos, 1 videos 10/10" [ref=e324] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-026
          - generic [ref=e325]:
            - generic [ref=e326]: Scene 27
            - generic [ref=e327]: 2026-03-31 12:08 · Miami
            - generic [ref=e328]: 9 photos, 1 videos
          - generic [ref=e330]: 10/10
        - button [ref=e331]:
          - img [ref=e332]
      - generic [ref=e335]:
        - link "Scene 28 2026-03-31 13:42 · 8 photos, 0 videos 8/8" [ref=e336] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-027
          - generic [ref=e337]:
            - generic [ref=e338]: Scene 28
            - generic [ref=e339]: 2026-03-31 13:42 ·
            - generic [ref=e340]: 8 photos, 0 videos
          - generic [ref=e342]: 8/8
        - button [ref=e343]:
          - img [ref=e344]
      - generic [ref=e347]:
        - link "Scene 29 2026-03-31 14:47 · Miami, Miami Beach 17 photos, 38 videos 55/55" [ref=e348] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-028
          - generic [ref=e349]:
            - generic [ref=e350]: Scene 29
            - generic [ref=e351]: 2026-03-31 14:47 · Miami, Miami Beach
            - generic [ref=e352]: 17 photos, 38 videos
          - generic [ref=e354]: 55/55
        - button [ref=e355]:
          - img [ref=e356]
      - generic [ref=e359]:
        - link "Scene 30 2026-03-31 17:50 · 2 photos, 2 videos 4/4" [ref=e360] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-029
          - generic [ref=e361]:
            - generic [ref=e362]: Scene 30
            - generic [ref=e363]: 2026-03-31 17:50 ·
            - generic [ref=e364]: 2 photos, 2 videos
          - generic [ref=e366]: 4/4
        - button [ref=e367]:
          - img [ref=e368]
      - generic [ref=e371]:
        - link "Scene 31 2026-03-31 18:32 · Coconut Grove 3 photos, 1 videos 4/4" [ref=e372] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-030
          - generic [ref=e373]:
            - generic [ref=e374]: Scene 31
            - generic [ref=e375]: 2026-03-31 18:32 · Coconut Grove
            - generic [ref=e376]: 3 photos, 1 videos
          - generic [ref=e378]: 4/4
        - button [ref=e379]:
          - img [ref=e380]
      - generic [ref=e383]:
        - link "Scene 32 2026-03-31 19:17 · Coconut Grove 1 photos, 0 videos 1/1" [ref=e384] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-031
          - generic [ref=e385]:
            - generic [ref=e386]: Scene 32
            - generic [ref=e387]: 2026-03-31 19:17 · Coconut Grove
            - generic [ref=e388]: 1 photos, 0 videos
          - generic [ref=e390]: 1/1
        - button [ref=e391]:
          - img [ref=e392]
      - generic [ref=e395]:
        - link "Scene 33 2026-04-01 10:32 · 151 photos, 43 videos 194/194" [ref=e396] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-032
          - generic [ref=e397]:
            - generic [ref=e398]: Scene 33
            - generic [ref=e399]: 2026-04-01 10:32 ·
            - generic [ref=e400]: 151 photos, 43 videos
          - generic [ref=e402]: 194/194
        - button [ref=e403]:
          - img [ref=e404]
      - generic [ref=e407]:
        - link "Scene 34 2026-04-01 12:49 · 3 photos, 7 videos 10/10" [ref=e408] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-033
          - generic [ref=e409]:
            - generic [ref=e410]: Scene 34
            - generic [ref=e411]: 2026-04-01 12:49 ·
            - generic [ref=e412]: 3 photos, 7 videos
          - generic [ref=e414]: 10/10
        - button [ref=e415]:
          - img [ref=e416]
      - generic [ref=e419]:
        - link "Scene 35 2026-04-01 13:39 · 7 photos, 0 videos 7/7" [ref=e420] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-034
          - generic [ref=e421]:
            - generic [ref=e422]: Scene 35
            - generic [ref=e423]: 2026-04-01 13:39 ·
            - generic [ref=e424]: 7 photos, 0 videos
          - generic [ref=e426]: 7/7
        - button [ref=e427]:
          - img [ref=e428]
      - generic [ref=e431]:
        - link "Scene 36 2026-04-01 14:17 · 5 photos, 2 videos 7/7" [ref=e432] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-035
          - generic [ref=e433]:
            - generic [ref=e434]: Scene 36
            - generic [ref=e435]: 2026-04-01 14:17 ·
            - generic [ref=e436]: 5 photos, 2 videos
          - generic [ref=e438]: 7/7
        - button [ref=e439]:
          - img [ref=e440]
      - generic [ref=e443]:
        - link "Scene 37 2026-04-01 15:50 · Coconut Grove 3 photos, 1 videos 4/4" [ref=e444] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-036
          - generic [ref=e445]:
            - generic [ref=e446]: Scene 37
            - generic [ref=e447]: 2026-04-01 15:50 · Coconut Grove
            - generic [ref=e448]: 3 photos, 1 videos
          - generic [ref=e450]: 4/4
        - button [ref=e451]:
          - img [ref=e452]
      - generic [ref=e455]:
        - link "Scene 38 2026-04-01 18:29 · Coconut Grove 35 photos, 5 videos 40/40" [ref=e456] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-037
          - generic [ref=e457]:
            - generic [ref=e458]: Scene 38
            - generic [ref=e459]: 2026-04-01 18:29 · Coconut Grove
            - generic [ref=e460]: 35 photos, 5 videos
          - generic [ref=e462]: 40/40
        - button [ref=e463]:
          - img [ref=e464]
      - generic [ref=e467]:
        - link "Scene 39 2026-04-02 09:36 · 8 photos, 1 videos 9/9" [ref=e468] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-038
          - generic [ref=e469]:
            - generic [ref=e470]: Scene 39
            - generic [ref=e471]: 2026-04-02 09:36 ·
            - generic [ref=e472]: 8 photos, 1 videos
          - generic [ref=e474]: 9/9
        - button [ref=e475]:
          - img [ref=e476]
      - generic [ref=e479]:
        - link "Scene 40 2026-04-02 11:48 · 4 photos, 0 videos 4/4" [ref=e480] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-039
          - generic [ref=e481]:
            - generic [ref=e482]: Scene 40
            - generic [ref=e483]: 2026-04-02 11:48 ·
            - generic [ref=e484]: 4 photos, 0 videos
          - generic [ref=e486]: 4/4
        - button [ref=e487]:
          - img [ref=e488]
      - generic [ref=e491]:
        - link "Scene 41 2026-04-03 12:11 · Wesley Chapel 1 photos, 0 videos 1/1" [ref=e492] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-040
          - generic [ref=e493]:
            - generic [ref=e494]: Scene 41
            - generic [ref=e495]: 2026-04-03 12:11 · Wesley Chapel
            - generic [ref=e496]: 1 photos, 0 videos
          - generic [ref=e498]: 1/1
        - button [ref=e499]:
          - img [ref=e500]
      - generic [ref=e503]:
        - link "Scene 42 2026-04-03 15:14 · 2 photos, 0 videos 2/2" [ref=e504] [cursor=pointer]:
          - /url: /project/2026-04-11-miami-trip-last-visit/scene/scene-041
          - generic [ref=e505]:
            - generic [ref=e506]: Scene 42
            - generic [ref=e507]: 2026-04-03 15:14 ·
            - generic [ref=e508]: 2 photos, 0 videos
          - generic [ref=e510]: 2/2
        - button [ref=e511]:
          - img [ref=e512]
```

# Test source

```ts
  1  | import { test, expect } from "@playwright/test";
  2  | 
  3  | const PROJECT_URL = "/project/2026-04-11-miami-trip-last-visit";
  4  | 
  5  | test.describe("Scene List", () => {
  6  |   test("shows all scenes with counts", async ({ page }) => {
  7  |     await page.goto(PROJECT_URL);
  8  |     await expect(page.locator("h1")).toContainText("Miami Trip");
  9  |     const scenes = page.locator("a[href*=scene]");
  10 |     await expect(scenes.first()).toBeVisible();
  11 |     expect(await scenes.count()).toBeGreaterThan(0);
  12 |   });
  13 | 
  14 |   test("scene card shows thumbnail", async ({ page }) => {
  15 |     await page.goto(PROJECT_URL);
  16 |     await expect(page.locator("a[href*=scene] img").first()).toBeVisible();
  17 |   });
  18 | 
  19 |   test("scene card shows selected count", async ({ page }) => {
  20 |     await page.goto(PROJECT_URL);
  21 |     await expect(page.locator("a[href*=scene]").first()).toContainText("/");
  22 |   });
  23 | 
  24 |   test("clicking scene navigates to grid", async ({ page }) => {
  25 |     await page.goto(PROJECT_URL);
  26 |     await page.locator("a[href*=scene]").first().click();
  27 |     await expect(page).toHaveURL(/\/scene\//);
  28 |   });
  29 | 
  30 |   test("back link returns to scenes", async ({ page }) => {
  31 |     await page.goto(PROJECT_URL);
  32 |     await page.locator("a[href*=scene]").first().click();
  33 |     await page.locator("a[href*=project]").first().click();
  34 |     await expect(page).toHaveURL(PROJECT_URL);
  35 |   });
  36 | });
  37 | 
  38 | test.describe("Scene Exclude & Restore", () => {
  39 |   test("exclude button is visible", async ({ page }) => {
  40 |     await page.goto(PROJECT_URL);
  41 |     await expect(page.locator("[data-testid=exclude-scene]").first()).toBeVisible();
  42 |   });
  43 | 
  44 |   test("clicking exclude hides scene and shows undo", async ({ page }) => {
  45 |     await page.goto(PROJECT_URL);
  46 |     const scenesBefore = await page.locator("a[href*=scene]").count();
  47 |     await page.locator("[data-testid=exclude-scene]").first().click();
  48 |     await page.waitForTimeout(300);
  49 |     const scenesAfter = await page.locator("a[href*=scene]").count();
  50 |     expect(scenesAfter).toBe(scenesBefore - 1);
  51 |     await expect(page.locator("text=Excluded")).toBeVisible();
  52 |   });
  53 | 
  54 |   test("undo restores excluded scene", async ({ page }) => {
  55 |     await page.goto(PROJECT_URL);
  56 |     const scenesBefore = await page.locator("a[href*=scene]").count();
  57 |     await page.locator("[data-testid=exclude-scene]").first().click();
  58 |     await page.waitForTimeout(300);
> 59 |     await page.getByRole("button", { name: "Undo" }).click();
     |                                                      ^ Error: locator.click: Test timeout of 30000ms exceeded.
  60 |     await page.waitForTimeout(300);
  61 |     expect(await page.locator("a[href*=scene]").count()).toBe(scenesBefore);
  62 |   });
  63 | });
  64 | 
```