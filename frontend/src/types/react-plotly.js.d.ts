declare module 'react-plotly.js' {
  import { Component } from 'react';
  import { PlotParams } from 'plotly.js';

  export interface Figure {
    data: Plotly.Data[];
    layout: Partial<Plotly.Layout>;
    frames?: Plotly.Frame[];
  }

  export interface PlotProps extends Partial<PlotParams> {
    data: Plotly.Data[];
    layout?: Partial<Plotly.Layout>;
    config?: Partial<Plotly.Config>;
    frames?: Plotly.Frame[];
    onClick?: (event: Readonly<Plotly.PlotMouseEvent>) => void;
    onClickAnnotation?: (event: Readonly<Plotly.ClickAnnotationEvent>) => void;
    onHover?: (event: Readonly<Plotly.PlotHoverEvent>) => void;
    onUnhover?: (event: Readonly<Plotly.PlotMouseEvent>) => void;
    onSelected?: (event: Readonly<Plotly.PlotSelectionEvent>) => void;
    onInitialized?: (figure: Readonly<Figure>, graphDiv: Readonly<HTMLElement>) => void;
    onUpdate?: (figure: Readonly<Figure>, graphDiv: Readonly<HTMLElement>) => void;
    onPurge?: (figure: Readonly<Figure>, graphDiv: Readonly<HTMLElement>) => void;
    onError?: (err: Readonly<Error>) => void;
    onRelayout?: (event: Readonly<Plotly.PlotRelayoutEvent>) => void;
    onRestyle?: (event: Readonly<Plotly.PlotRestyleEvent>) => void;
    onRedraw?: () => void;
    onAfterExport?: () => void;
    onAfterPlot?: () => void;
    onAnimated?: () => void;
    onAnimatingFrame?: (event: Readonly<Plotly.FrameAnimationEvent>) => void;
    onAnimationInterrupted?: () => void;
    onAutoSize?: () => void;
    onBeforeExport?: () => void;
    onButtonClicked?: (event: Readonly<Plotly.ButtonClickEvent>) => void;
    onDoubleClick?: () => void;
    onFramework?: () => void;
    onSliderChange?: (event: Readonly<Plotly.SliderChangeEvent>) => void;
    onSliderEnd?: (event: Readonly<Plotly.SliderEndEvent>) => void;
    onSliderStart?: (event: Readonly<Plotly.SliderStartEvent>) => void;
    onTransitioning?: () => void;
    onTransitionInterrupted?: () => void;
    onWebGlContextLost?: () => void;
    divId?: string;
    className?: string;
    style?: React.CSSProperties;
    useResizeHandler?: boolean;
    debug?: boolean;
    onBeforeHover?: (event: Readonly<Plotly.PlotMouseEvent>) => boolean | void;
    onDeselect?: () => void;
    onLegendClick?: (event: Readonly<Plotly.LegendClickEvent>) => boolean;
    onLegendDoubleClick?: (event: Readonly<Plotly.LegendClickEvent>) => boolean;
    revision?: number;
  }

  export default class Plot extends Component<PlotProps> {}
}
