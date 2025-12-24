import { SigmaContainer } from "@react-sigma/core";
import { GraphLoader } from "./GraphLoader";
import { HoverCoreNode } from "./HoverCoreNode";
import { useMemo } from "react";
//import { SigmaAutoResize } from "./SigmaAutoResize";



export function GraphCanvas() { 
    
    const sigmaSettings = useMemo(
        () => ({
            defaultNodeColor: "#9aa0a6",
            defaultEdgeColor: "#9aa0a6",
            labelRenderedSizeThreshold: 10,
            enableEdgeEvents: true,
            defaultDrawNodeHover: () => {},
        }),
        []
      );

    return (
        <div style={{ width: "100%", height: "100%" }}>
        <SigmaContainer
            style={{ width: "100%", height: "100%" }}
            settings={sigmaSettings}
        >
            <GraphLoader />
            <HoverCoreNode />
        </SigmaContainer>
        </div>
    );
}
