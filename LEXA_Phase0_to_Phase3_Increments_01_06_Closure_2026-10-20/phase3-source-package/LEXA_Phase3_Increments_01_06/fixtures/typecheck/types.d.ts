declare module "react" {
  export type ReactNode = any;
  export type FormEvent<T = any> = { preventDefault(): void; target: T };
  export type SetStateAction<S> = S | ((previous: S) => S);
  export type Dispatch<A> = (value: A) => void;
  export function useState<S>(initial: S | (() => S)): [S, Dispatch<SetStateAction<S>>];
  export function useEffect(effect: () => void | (() => void), deps?: readonly unknown[]): void;
  export function useCallback<T extends (...args: any[]) => any>(callback: T, deps: readonly unknown[]): T;
}
declare module "next/link" { const Link: (props: any) => JSX.Element; export default Link; }
declare module "next/navigation" { export function useRouter(): { replace(path: string): void; refresh(): void; push(path: string): void }; }
declare namespace JSX {
  interface Element {}
  interface ElementChildrenAttribute { children: {}; }
  interface IntrinsicElements {
    input: { onChange?: (event: { target: { value: string; checked: boolean } }) => void; [key: string]: any };
    select: { onChange?: (event: { target: { value: string; checked: boolean } }) => void; [key: string]: any };
    textarea: { onChange?: (event: { target: { value: string; checked: boolean } }) => void; [key: string]: any };
    [elementName: string]: any;
  }
}
