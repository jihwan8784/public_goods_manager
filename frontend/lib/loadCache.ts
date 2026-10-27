// useLoad 가 최근 결과를 주소별로 기억하는 곳. 메모리에만 있어 새로고침·로그아웃 때 비워진다.
// 저장·변경 요청(POST 등)이 성공하면 api() 가 통째로 비운다 → 수정 화면에 옛 값이 보이지 않음.
const MAX = 60;
const cache = new Map<string, { data: unknown; json: string }>();

export function cacheGet(path: string) {
  return cache.get(path);
}

export function cacheSet(path: string, data: unknown, json: string) {
  cache.delete(path);
  cache.set(path, { data, json });
  if (cache.size > MAX) cache.delete(cache.keys().next().value as string);
}

export function cacheClear() {
  cache.clear();
}
