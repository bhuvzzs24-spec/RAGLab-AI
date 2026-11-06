import original from './official-halftone.json';
// Licensed project-local adaptation: headline text/ink and background only. The stored
// upstream document, ring geometry, drawing functions and clock stay intact.
export const raglabDocument=original.html
 .replaceAll('One Wall, Twelve Plates','RAGLAB AI — RETRIEVE. EVALUATE. OPTIMIZE.')
 .replace("s:'ONE WALL', top:930,  w:1132, fill:'#c0402c'","s:'RAGLAB AI', top:930,  w:1132, fill:'#E7B0DE'")
 .replace("s:'TWELVE PLATES'","s:'RETRIEVE. EVALUATE. OPTIMIZE.'")
 .replaceAll('background:#000000','background:#120715')
 .replaceAll('background: #000000','background: #120715')
 .replace("ctx.fillStyle = '#000000';","ctx.fillStyle = '#120715';");
