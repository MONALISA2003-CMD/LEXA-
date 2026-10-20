declare module "react" {
  export type FormEvent = { preventDefault(): void };
  export function useEffect(effect: () => void | (() => void), deps?: unknown[]): void;
  export function useMemo<T>(factory: () => T, deps: unknown[]): T;
  export function useState<T>(initial: T | (() => T)): [T, (value: T | ((prev: T) => T)) => void];
}
declare module "react/jsx-runtime" {
  export const Fragment: unknown;
  export function jsx(...args: unknown[]): unknown;
  export function jsxs(...args: unknown[]): unknown;
}

declare namespace JSX {
  interface IntrinsicElements { [elemName: string]: any; }
}
