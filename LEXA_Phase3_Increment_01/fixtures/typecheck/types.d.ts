declare module "react" {
  export type ReactNode = any;
  export type FormEvent<T = any> = { preventDefault(): void; target: T };
  export type SetStateAction<S> = S | ((previous: S) => S);
  export type Dispatch<A> = (value: A) => void;
  export function useState<S>(initial: S | (() => S)): [S, Dispatch<SetStateAction<S>>];
  export function useEffect(effect: () => void | (() => void), deps?: unknown[]): void;
  export function useCallback<T extends (...args: any[]) => any>(callback: T, deps: unknown[]): T;
}
declare namespace JSX {
  interface Element {}
  interface ElementChildrenAttribute { children: {}; }
  interface IntrinsicElements {
    [elementName: string]: {
      [attributeName: string]: any;
      children?: any;
      onChange?: (event: { target: { value: string } }) => void;
      onSubmit?: (event: import("react").FormEvent<HTMLFormElement>) => void;
      onClick?: () => void;
    };
  }
}
