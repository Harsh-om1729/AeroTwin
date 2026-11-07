import { createContext, useContext } from 'react';

// Shared Simple/Detailed view state (see viewMode.jsx).
export const ViewCtx = createContext({ simple: true, setSimple: () => {} });
export const useSimple = () => useContext(ViewCtx).simple;
