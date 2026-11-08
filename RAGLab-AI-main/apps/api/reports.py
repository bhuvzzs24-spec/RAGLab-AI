"""On-demand PDF reports from persisted measurements; no external chart service."""
import io
import json
from html import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether
from reportlab.graphics.shapes import Drawing,Rect,String,Line,Circle
from evaluation import METHODOLOGY
from adaptive import uncertainty

CYAN=colors.HexColor('#400849');CORAL=colors.HexColor('#FF5A0A');INK=colors.HexColor('#241426')

def benchmark_pdf(run,measurements):
    stream=io.BytesIO();styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SmallBody',fontName='Helvetica',fontSize=8,leading=12,textColor=INK,spaceAfter=7))
    styles.add(ParagraphStyle(name='TableBody',fontName='Helvetica',fontSize=8,leading=10,textColor=INK,spaceAfter=0))
    styles['Title'].textColor=INK;styles['Heading2'].textColor=CYAN
    def p(value,style='SmallBody'):
        # Built-in PDF fonts: normalize unsupported glyphs instead of producing missing boxes.
        value=str(value).replace('×','x').replace('–','-').replace('—','-').replace('·',' / ')
        return Paragraph(escape(value.encode('ascii','replace').decode()).replace('\n','<br/>'),styles[style])
    def fmt(v,d=3):return 'Not evaluated' if v is None else f'{v:.{d}f}'
    story=[p('RAGLab | Research report','Title'),p(run['name'],'Heading2'),
           p('PROVISIONAL - includes unreviewed evidence labels' if run['snapshot']['provisional'] else 'Reviewed annotation scope - human attestations recorded'),
           p(f"Run {run['id']}\nCreated {run['created']} UTC | Status {run['status']}\nDataset {run['snapshot']['name']} revision {run['snapshot']['revision']}\nFingerprint {run['snapshot']['fingerprint']}"),
           p('Scope and reproducibility','Heading2')]
    settings=run['settings'];questions=run['snapshot']['questions']
    story.append(p(f"Split: {run['snapshot'].get('split','all')}. Unique questions: {len(questions)}; reviewed: {run['snapshot']['reviewed_questions']}. Completed measurements: {run['completed_measurements']}/{run['total_measurements']}. Fixed top-k: {settings['top_k']}; repetitions: {settings['repetitions']}; seed: {settings['seed']}; cosine cutoff: {settings['min_score']}; evidence overlap: {settings['evidence_overlap']}."))
    provenance=settings.get('adaptive_provenance')
    if provenance:
        story.append(p(f"Adaptive stage: {provenance['stage']} | search {provenance['search_id']}"))
        frozen=provenance.get('frozen_selection')
        if frozen:story.append(p(f"Selection frozen on validation before test queries. Seal: {frozen['sha256']}\nValidation fingerprint: {frozen['selection_fingerprint']}"))
    story += [p('Measured configuration comparison','Heading2')]
    configs=run['configs'];complete=[c for c in configs if c['status']=='completed']
    tp=lambda value:p(value,'TableBody')
    rows=[[tp(x) for x in ['Configuration','P@k','R@k','MRR','Query ms','Build ms','N*']]]
    for c in configs:
        m=c['metrics'];cfg=c['config']
        label=f"{cfg['model_id']} / {cfg['strategy']} / {cfg['budget']}\n{c['status']}"
        rows.append([tp(label),*[tp(fmt(m.get(k))) for k in ['precision_at_k','recall_at_k','mrr']],
            tp(fmt(m.get('latency_mean_ms'),2)),tp('Reused' if c['indexing_time_ms'] is None and c['index_cache_reused'] else fmt(c['indexing_time_ms'],1)),tp(m.get('unique_answerable_questions','-'))])
    table=Table(rows,colWidths=[157,40,40,40,61,64,29],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#F5E7F2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),3),('LINEBELOW',(0,0),(-1,0),1,CYAN),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F7F3F8')])]))
    story += [table,p('*N is unique answerable questions; repeated queries are not independent samples. Missing metrics remain unevaluated. Reused index build time is not measured anew.'),PageBreak(),p('Actual metric charts','Heading2')]
    if complete:
        drawing=Drawing(490,max(90,24*len(complete)+40));h=drawing.height
        for i,c in enumerate(complete):
            y=h-30-i*24;cfg=c['config'];v=c['metrics'].get('recall_at_k')
            drawing.add(String(0,y,f"{cfg['model_id']} {cfg['strategy']} {cfg['budget']}",fontName='Helvetica',fontSize=8,fillColor=INK))
            if v is not None:
                drawing.add(Rect(178,y-3,250*v,12,fillColor=CYAN,strokeColor=None));drawing.add(String(435,y,fmt(v),fontName='Helvetica',fontSize=8,fillColor=INK))
        drawing.add(String(178,h-12,'Recall@k (0 to 1)',fontName='Helvetica',fontSize=9,fillColor=INK));story.append(drawing)
        scatter=Drawing(490,190);scatter.add(Line(45,25,470,25,strokeColor=INK));scatter.add(Line(45,25,45,165,strokeColor=INK))
        max_ms=max(c['metrics'].get('latency_mean_ms') or 0 for c in complete) or 1
        for c in complete:
            m=c['metrics'];recall=m.get('recall_at_k');latency=m.get('latency_mean_ms')
            if recall is not None and latency is not None:scatter.add(Circle(45+latency/max_ms*415,25+recall*135,3,fillColor=CORAL,strokeColor=None))
        scatter.add(String(45,5,f'Mean retrieval latency: 0 to {max_ms:.1f} ms',fontName='Helvetica',fontSize=9));scatter.add(String(45,176,'Recall@k: vertical axis 0 to 1; each dot is a completed configuration',fontName='Helvetica',fontSize=8));
        for v in [0,.5,1]:scatter.add(String(20,25+v*135,f'{v:.1f}',fontName='Helvetica',fontSize=8))
        story.append(scatter)
    else:story.append(p('No completed configurations; charts are unavailable.'))
    if len(complete)>10:story.append(PageBreak())
    story += [p('Uncertainty and repeatability','Heading2')]
    for c in complete:
        records=[m for m in measurements if m['config_id']==c['id']];u=uncertainty(records,settings['seed']);ci=u['intervals']['recall_at_k'];cfg=c['config']
        interval=ci['ci95'];interval_text=f"[{interval[0]:.3f}, {interval[1]:.3f}]" if interval else 'unavailable (fewer than two unique answerable questions)'
        story.append(p(f"{cfg['model_id']} / {cfg['strategy']} / {cfg['budget']}: recall 95% bootstrap interval {interval_text}; N={ci['unique_questions']}; repeated questions={u['repeatability']['repeated_questions']}; metric consistency={u['repeatability']['quality_consistent']}."))
    story += [p('Intervals use 1,000 seeded bootstrap draws over per-question means. They are exploratory, unadjusted for multiple comparisons and do not establish superiority. Small datasets give unstable intervals; evidence-related questions may remain correlated. Repeatability refers to within-run retrieval quality, not constant latency.'),PageBreak(),p('Methodology and limitations','Heading2')]
    for key,value in METHODOLOGY.items():story.append(p(key.replace('_',' ').upper()+': '+value))
    story.append(p('LLM status: '+('Optional generation requested; consult generation statuses and exact-match counts in JSON export.' if settings['generate_answers'] else 'Disabled. Live generated Q&A and semantic groundedness are not verified by this report.')))
    story.append(p('Do not tune configurations on held-out test results. Repeated adaptive searches on the same test partition weaken its independence. Split guards detect exact duplicates, explicit groups and overlapping evidence, not all semantic paraphrases. Review related questions manually. All latency measurements reflect this host and cache state.'))
    for c in configs:
        if c.get('error'):story.append(p(f"Failure {c['id']}: {c['error']}"))
    human=run.get('human_answer_evaluation')
    if human:
        story.append(PageBreak())
        story.append(p('Optional human answer evaluation','Heading2'))
        story.append(p(f"Reviewed answers: {human['reviewed_answers']}/{human['stored_answers']}. Human correctness: {fmt(human['correctness'])} (N={human['correctness_n']}); human groundedness: {fmt(human['groundedness'])} (N={human['groundedness_n']}). As of {human['as_of']}."))
        story.append(p(human['limitation']))
        for label,text in human['rubric'].items():story.append(p(label+': '+text))
    story.append(p('Model versions and runtime','Heading2'))
    for model,spec in settings.get('model_registry',{}).items():
        story.append(p(f"{model}: {spec['repository']}\nPinned revision {spec['revision']} | {spec['dimensions']} dimensions | normalized vectors\nQuery prefix: {spec.get('query_prefix') or '(none)'}"))
    for key in ['runtime','packages','evaluation_version','timing_mode']:story.append(p(f"{key}: {json.dumps(settings.get(key),sort_keys=True)}"))
    story.append(p('Source integrity','Heading2'))
    for source in run['snapshot']['sources']:story.append(p(f"{source['name']} | {source['id']}\nSHA256 {source['sha256']}"))
    story.append(p('Reproduce using the JSON export (immutable snapshot, settings, model revisions, configurations and per-query measurements). CSV contains measured rows. Original private uploads and downloaded model weights are excluded from source control.'))
    def footer(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(CYAN);canvas.line(32,30,A4[0]-32,30);canvas.setFont('Helvetica',8);canvas.setFillColor(INK)
        canvas.drawString(32,18,'RAGLab - actual measurements / '+run['id'][:8]);canvas.drawRightString(A4[0]-32,18,f'Page {doc.page}');canvas.restoreState()
    SimpleDocTemplate(stream,pagesize=A4,rightMargin=32,leftMargin=32,topMargin=34,bottomMargin=43,title='RAGLab experiment report',author='RAGLab').build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()
