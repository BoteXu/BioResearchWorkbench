# Server-only scientific source; runtime validation NOT_RUN_THIS_UPGRADE.
suppressPackageStartupMessages(library(jsonlite))
argv <- commandArgs(TRUE)
job <- fromJSON(argv[1], simplifyVector = FALSE)
out <- argv[2]
p <- job$parameters
I <- job$inputs
key <- job$analysis_id
ctx <- job$context
set.seed(p$seed)
need <- function(pkg) {
    if (!requireNamespace(pkg, quietly = TRUE)) 
        stop(paste("Use existing server environment; missing", pkg))
}
need("limma")
tab <- function(id) {
    h <- names(read.delim(I[[id]], nrows=0, check.names=FALSE))
    types <- rep(NA_character_, length(h));names(types)<-h
    types[grepl("(^|_)(id|gene|protein|variant)$|^source$|^target$|^SNP$",h)]<-"character"
    types[h%in%c('group','cell_type','cluster','chromosome','chrom','condition','study_id')]<-'character'
    x <- read.delim(I[[id]], check.names=FALSE, stringsAsFactors=FALSE, colClasses=types)
    for (name in intersect(names(x), c("reviewed","tissue_present","ld_clumped","unrelated","offset_validated","normal_reviewed","read_bias_assessed","identity_ambiguous"))) {
        if (anyNA(x[[name]]) || !all(x[[name]] %in% c(TRUE,FALSE,0,1,"TRUE","FALSE","True","False","true","false"))) stop(paste("Invalid boolean evidence",name))
        x[[name]] <- tolower(as.character(x[[name]])) %in% c("true","1")
    }
    if (!nrow(x) || anyDuplicated(names(x))) 
        stop(paste("Empty/duplicate columns", id))
    x
}
req <- function(x, cols) {
    if (!all(cols %in% names(x))) 
        stop(paste("Missing columns", paste(setdiff(cols, names(x)), collapse = ",")))
    x
}
mat <- function(id = "matrix", counts = FALSE) {
    h <- names(read.delim(I[[id]], nrows=0, check.names=FALSE))
    cls<-rep(NA_character_,length(h));cls[1]<-"character"
    z<-read.delim(I[[id]],check.names=FALSE,colClasses=cls,stringsAsFactors=FALSE)
    if (anyDuplicated(z[[1]]) || anyNA(z[[1]]) || anyDuplicated(names(z)[-1])) 
        stop("Duplicate/empty matrix axis")
    r <- as.matrix(z[, -1, drop = FALSE])
    storage.mode(r) <- "double"
    rownames(r) <- z[[1]]
    if (any(!is.finite(r))) 
        stop("Nonfinite matrix; do not silently impute")
    if (counts && (any(r < 0) || any(r != round(r)))) 
        stop("Require raw nonnegative integer counts")
    r
}
meta <- function(repeated = FALSE) {
    s <- req(tab("samples"), c("sample_id", "unit_id"))
    if (anyDuplicated(s$sample_id) || anyNA(s$unit_id) || any(!nzchar(s$unit_id))) 
        stop("Sample/unit identity invalid")
    if (!repeated && anyDuplicated(s$unit_id)) 
        stop("Aggregate to independent biological units or choose a repeated-unit implementation")
    if (anyNA(s$sample_id) || any(!nzchar(s$sample_id))) stop("Missing sample IDs")
    for (name in intersect(names(s),names(ctx$variable_types))) {
        kind<-ctx$variable_types[[name]]
        if(kind=="categorical") s[[name]]<-factor(s[[name]])
        else if(kind=="continuous") {v<-suppressWarnings(as.numeric(s[[name]]));if(any(!is.finite(v)))stop(paste("Nonfinite continuous covariate",name));s[[name]]<-v}
    }
    rownames(s) <- s$sample_id
    s
}
aligned <- function(x, s) {
    if (!setequal(colnames(x), s$sample_id)) 
        stop("Exact sample denominator mismatch")
    x[, s$sample_id, drop = FALSE]
}
design <- function(s, formula = p$design) {
    if (!is.character(formula) || length(formula) != 1 || !grepl("^~[A-Za-z0-9_ +*:.-]+$", formula)) 
        stop("Only reviewed column-name model formula supported")
    vars<-all.vars(as.formula(formula));if(!all(vars%in%names(s))||anyNA(s[,vars,drop=FALSE]))stop("Missing design variables; no silent sample omission")
    d <- model.matrix(as.formula(formula), s, na.action=na.fail)
    if(nrow(d)!=nrow(s))stop("Design lost biological units")
    if (qr(d)$rank < ncol(d) || nrow(d) <= ncol(d)) 
        stop("Confounded design or no residual degrees of freedom")
    d
}
contrast <- function(d) {
    v <- unlist(p$contrast)
    if (!is.numeric(v) || is.null(names(v)) || !all(names(v) %in% colnames(d)) || !any(v != 0)) 
        stop("Explicit coefficient->numeric contrast required")
    c <- rep(0, ncol(d))
    names(c) <- colnames(d)
    c[names(v)] <- v
    c
}
fits <- function(x, s, d = design(s), block = NULL) {
    x <- aligned(x, s)
    if (is.null(block)) 
        f <- limma::lmFit(x, d)
    else {
        dc <- limma::duplicateCorrelation(x, d, block = block)
        f <- limma::lmFit(x, d, block = block, correlation = dc$consensus.correlation)
    }
    c <- contrast(d)
    f <- limma::eBayes(limma::contrasts.fit(f, c))
    r <- limma::topTable(f, number = Inf, sort.by = "none", confint = TRUE)
    r$feature_id <- rownames(r)
    if(any(!is.finite(r$logFC))||any(!is.finite(r$P.Value)))stop("limma fit contains unassessed/nonfinite tested features")
    list(result = r, design = data.frame(sample_id = rownames(d), d, check.names = FALSE), fit = f)
}
cover <- function(sets, features) {
    data.frame(set = names(sets), reference_size = lengths(sets), observed_size = vapply(sets, function(z) sum(z %in% 
        features), integer(1)))
}
sets_in <- function() {
    z <- req(tab("gene_sets"), c("set", "feature_id"))
    lapply(split(as.character(z$feature_id), z$set), unique)
}
save4 <- function(a, b, c, d, metrics) {
    objects <- list(a, b, c, d)
    roles <- unlist(job$required_roles)
    stopifnot(length(roles) == 4)
    manifest <- list()
    for (i in seq_along(roles)) {
        z <- objects[[i]]
        if (is.matrix(z)) {
            z <- data.frame(feature_id = rownames(z), z, check.names = FALSE)
        }
        if (!is.data.frame(z) || !ncol(z)) 
            stop("Real structured result required")
        name <- paste0(roles[i], ".tsv")
        write.table(z, file.path(out, name), sep = "\t", quote = FALSE, row.names = FALSE, na = "NA")
        manifest[[roles[i]]] <- name
    }
    write_json(manifest, file.path(out, "outputs.private.json"), auto_unbox = TRUE, pretty = TRUE)
    pkgs <- loadedNamespaces()
    versions <- as.list(vapply(pkgs, function(z) as.character(packageVersion(z)), character(1)))
    write_json(list(fit_completed = TRUE, metrics = metrics, versions = versions, scientific_acceptance = "NOT_ESTABLISHED", 
        warnings = warnings_seen), file.path(out, "diagnostics.private.json"), auto_unbox = TRUE, pretty = TRUE)
}
warnings_seen <- character()
options(warn = 1)
withCallingHandlers({
    if (key %in% c("camera_sets", "gsva_scores", "ssgsea_scores")) {
        x <- mat()
        s <- meta()
        x <- aligned(x, s)
        gs <- sets_in()
        full_feature_qc<-data.frame(feature_id=rownames(x),variance=apply(x,1,var))
        keep_variable<-full_feature_qc$variance>0
        if(!any(keep_variable))stop("No variable genes remain for pathway analysis")
        x<-x[keep_variable,,drop=FALSE]
        write.table(full_feature_qc,file.path(out,"pathway_feature_qc.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
        cv <- cover(gs, rownames(x))
        ok <- cv$observed_size >= p$min_set_size
        gs <- gs[ok]
        if (!length(gs)) 
            stop("No set passes explicit coverage threshold")
        if (key == "camera_sets") {
            d <- design(s)
            need("limma")
            weights<-NULL
            if(ctx$scale=="voom_logCPM"){
                if(is.null(I$voom_weights))stop("CAMERA on voom input requires the matching precision weights")
                weights<-aligned(mat("voom_weights"),s);if(!all(rownames(x)%in%rownames(weights)))stop("Voom precision-weight gene universe mismatch");weights<-weights[rownames(x),,drop=FALSE];if(any(weights<=0))stop("Invalid voom precision weights")
            }
            z <- limma::camera(x, index = limma::ids2indices(gs, rownames(x)), design = d, contrast = contrast(d),weights=weights)
            z$set <- rownames(z)
            save4(z, data.frame(sample_id = rownames(d), d), cv, data.frame(set = names(gs), n = lengths(gs)), 
                list(tested_sets = nrow(z), design_rank = qr(d)$rank, residual_df = nrow(d) - ncol(d)))
        }
        else {
            need("GSVA")
            if (key == "gsva_scores") {
                gp <- GSVA::gsvaParam(x, gs, kcdf = p$kcdf, minSize = p$min_set_size, maxSize = p$max_set_size)
            }
            else {
                gp <- GSVA::ssgseaParam(x, gs, minSize = p$min_set_size, maxSize = p$max_set_size, normalize = p$normalize)
            }
            z <- GSVA::gsva(gp, verbose = FALSE)
            activity_contrasts <- fits(z, s)
            save4(z, cv, data.frame(sample_id = colnames(z), score_mean = colMeans(z), score_sd = apply(z, 
                2, sd)), activity_contrasts$result, list(scored_sets = nrow(z), samples = ncol(z), finite_fraction = mean(is.finite(z))))
        }
    }
    else if (key %in% c("tf_activity", "kinase_activity")) {
        need("decoupleR")
        x <- mat()
        s <- meta()
        x <- aligned(x, s)
        if (key == "kinase_activity") {
            total <- aligned(mat("protein_matrix"), s)
            mapping <- req(tab("site_map"), c("site", "protein"))
            if (anyDuplicated(mapping$site) || !all(rownames(x) %in% mapping$site)) 
                stop("Kinase phosphosite mapping incomplete")
            mapping <- mapping[match(rownames(x), mapping$site), ]
            if (!all(mapping$protein %in% rownames(total))) 
                stop("Kinase total-protein denominator missing")
            x <- x - total[mapping$protein, , drop = FALSE]
        }
        net <- req(tab("regulatory_network"), c("source", "target", "mor"))
        if (anyDuplicated(net[c("source", "target")])) 
            stop("Duplicate regulatory edges require reviewed resolution")
        act <- decoupleR::run_ulm(x, net, .source = "source", .target = "target", .mor = "mor", minsize = p$min_targets)
        if(anyDuplicated(act[c("source","condition")])||nrow(act)!=length(unique(act$source))*ncol(x)||!setequal(unique(act$condition),colnames(x)))stop("Regulator activity matrix is incomplete; xtabs must not fill absent fits with zero")
        wide <- xtabs(score ~ source + condition, act)
        cv <- do.call(rbind, lapply(split(net, net$source), function(g) data.frame(source = g$source[1], 
            reference_targets = nrow(g), observed_targets = sum(g$target %in% rownames(x)))))
        f <- fits(as.matrix(wide), s)
        save4(as.data.frame(act), cv, f$result, f$design, list(regulators = nrow(wide), targets_covered = sum(net$target %in% 
            rownames(x)), samples = ncol(wide)))
    }
    else if (key %in% c("protein_complexes", "ptm_adjustment")) {
        x <- mat()
        s <- meta()
        x <- aligned(x, s)
        if (ctx$scale != "log2_abundance") 
            stop("Require normalized log2 abundance; no automatic log conversion")
        if (key == "protein_complexes") {
            mp <- req(tab("complex_members"), c("complex", "protein"))
            sets <- lapply(split(mp$protein, mp$complex), unique)
            cv <- cover(sets, rownames(x))
            keep <- cv$observed_size >= p$min_members
            sets <- sets[keep]
            if (!length(sets)) 
                stop("Insufficient complex membership")
            agg <- t(vapply(sets, function(ids) colMeans(x[intersect(ids, rownames(x)), , drop = FALSE]), 
                numeric(ncol(x))))
            colnames(agg) <- colnames(x)
            f <- fits(agg, s)
            member <- fits(x, s)$result
            heterogeneity <- vapply(sets, function(ids) {
                a <- x[intersect(ids, rownames(x)), , drop = FALSE]
                if (nrow(a) < 2) return(NA_real_)
                mean(apply(a, 2, sd))
            }, numeric(1))
            save4(f$result, cv, member, data.frame(feature_id = rownames(agg),
                aggregate_profile_sd = apply(agg, 1, sd),
                mean_within_sample_member_sd = heterogeneity,
                interpretation = "descriptive_member_abundance_heterogeneity_not_complex_assembly"),
                list(complexes = nrow(agg), samples = ncol(agg), covered_members = sum(cv$observed_size)))
        }
        else {
            total <- aligned(mat("protein_matrix"), s)
            mp <- req(tab("site_map"), c("site", "protein"))
            if (anyDuplicated(mp$site) || !all(rownames(x) %in% mp$site)) 
                stop("PTM requires one reviewed parent protein per site")
            mp <- mp[match(rownames(x), mp$site), ]
            if (!all(mp$protein %in% rownames(total))) 
                stop("Missing matched total-protein denominator")
            adj <- x - total[mp$protein, , drop = FALSE] * p$protein_adjustment_weight
            f <- fits(adj, s)
            pf <- fits(total, s)
            save4(f$result, pf$result, mp, data.frame(site = rownames(x), site_sd = apply(x, 1, sd), 
                adjusted_sd = apply(adj, 1, sd)), list(sites = nrow(x), samples = ncol(x), same_sample_pairs = ncol(x)))
        }
    }
    else if (key == "cell_fraction_contrasts") {
        cnt <- mat("cell_counts", TRUE)
        s <- meta()
        cnt <- aligned(cnt, s)
        den <- colSums(cnt)
        if (any(den <= 0) || p$pseudocount <= 0) 
            stop("Zero denominator or invalid pseudocount")
        prop <- (cnt + p$pseudocount)/(matrix(den, nrow(cnt), ncol(cnt), byrow = TRUE) + 2 * p$pseudocount)
        if(p$composition_transform=="logit") transformed<-qlogis(prop)
        else if(p$composition_transform=="asin_sqrt") transformed<-asin(sqrt(cnt/matrix(den,nrow(cnt),ncol(cnt),byrow=TRUE)))
        else stop("Select logit or asin_sqrt composition transform")
        f <- fits(transformed, s)
        save4(f$result, data.frame(sample_id = s$sample_id, unit_id = s$unit_id, total_cells = den), 
            f$design, data.frame(celltype = rownames(cnt), zero_units = rowSums(cnt == 0)), list(independent_units = nrow(s), 
                min_denominator = min(den), tested_types = nrow(cnt)))
    }
    else if (key == "cross_study_meta") {
        need("metafor")
        z <- req(tab("study_effects"), c("study_id", "effect", "se", "estimand"))
        ov <- req(tab("study_overlap"), c("study1", "study2", "overlap_n"))
        if (anyDuplicated(z$study_id) || any(z$se <= 0) || any(z$estimand != p$estimand) || nrow(z) < 
            3) 
            stop("Meta units/estimands/SE invalid")
        if (any(ov$overlap_n > 0)) 
            stop("Overlapping cohorts require an explicitly modeled covariance; independent REML route refuses them")
        expected_pairs <- apply(combn(sort(z$study_id), 2), 2, paste, collapse="|")
        actual_pairs <- apply(ov[, c("study1", "study2"), drop=FALSE], 1, function(v) paste(sort(v), collapse="|"))
        if (!setequal(expected_pairs, actual_pairs) || anyDuplicated(actual_pairs) || any(ov$overlap_n < 0))
            stop("Complete unique pairwise cohort-overlap denominator required")
        m <- metafor::rma(yi = z$effect, sei = z$se, method = p$tau_method)
        l <- as.data.frame(metafor::leave1out(m))
        l$omitted_study <- z$study_id
        save4(data.frame(effect = as.numeric(m$b), se = m$se, ci_lower = m$ci.lb, ci_upper = m$ci.ub, 
            p = m$pval), data.frame(tau2 = m$tau2, I2 = m$I2, Q = m$QE, Q_p = m$QEp), ov, l, list(studies = nrow(z), 
            tau2 = m$tau2, I2 = m$I2))
    }
    else if (key %in% c("longitudinal_effects", "impulse_response")) {
        s <- meta(key == "longitudinal_effects")
        x <- aligned(mat(), s)
        t <- s[[p$time_column]]
        if (!is.numeric(t) || length(unique(t)) <= p$time_df + 1 || anyNA(t)) 
            stop("Insufficient distinct time coverage")
        base <- design(s)
        basis <- splines::ns(t, df = p$time_df)
        colnames(basis) <- paste0("time", seq_len(ncol(basis)))
        if (p$time_group != "none") {
            if (!p$time_group %in% names(s)) stop("Selected time-by-group column missing")
            groups_time <- model.matrix(reformulate(p$time_group), s)[, -1, drop=FALSE]
            interactions <- do.call(cbind, lapply(seq_len(ncol(groups_time)), function(j) {
                b <- basis * groups_time[, j]
                colnames(b) <- paste0(colnames(groups_time)[j], ":", colnames(basis))
                b
            }))
            basis <- cbind(basis, interactions)
        }
        d <- cbind(base, basis)
        if (qr(d)$rank < ncol(d) || nrow(d) <= ncol(d)) 
            stop("Time design rank/df invalid")
        if (key == "longitudinal_effects") {
            if (!anyDuplicated(s$unit_id)) 
                stop("Longitudinal route requires actual repeated units")
            dc <- limma::duplicateCorrelation(x, d, block = s$unit_id)
            f <- limma::lmFit(x, d, block = s$unit_id, correlation = dc$consensus.correlation)
        }
        else {
            f <- limma::lmFit(x, d)
        }
        ef <- limma::eBayes(f)
        omnibus <- limma::topTable(ef, coef = (ncol(base) + 1):ncol(d), number = Inf, sort.by = "none")
        write.table(data.frame(feature_id = rownames(omnibus), omnibus), file.path(out, "time_omnibus.tsv"), 
            sep = "\t", quote = FALSE, row.names = FALSE)
        tested <- limma::eBayes(limma::contrasts.fit(f, contrast(d)))
        z <- limma::topTable(tested, number = Inf, sort.by = "none", confint = TRUE)
        z$feature_id <- rownames(z)
        curves <- f$coefficients %*% t(d)
        colnames(curves)<-s$sample_id;rownames(curves)<-rownames(x)
        write.table(data.frame(feature_id=rownames(x),curves,check.names=FALSE),file.path(out,"fitted_time_curves.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
        write.table(data.frame(sample_id=s$sample_id,unit_id=s$unit_id,time=t),file.path(out,"time_coverage.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
        save4(z, if(key=="impulse_response")data.frame(feature_id=rownames(x),curves,check.names=FALSE)else data.frame(sample_id=s$sample_id,d,check.names=FALSE), if(key=="impulse_response")data.frame(sample_id=s$sample_id,unit_id=s$unit_id,time=t)else data.frame(feature_id=rownames(x),residual_sd=f$sigma),data.frame(feature_id=rownames(x),residual_df=f$df.residual,method="spline_model_per_run_diagnostics"), list(genes = nrow(x), independent_units = length(unique(s$unit_id)), 
            time_points = length(unique(t)), residual_df = min(f$df.residual)))
    }
    else if (key %in% c("differential_binding", "translation_efficiency")) {
        need("edgeR")
        s <- meta(key == "translation_efficiency")
        x <- aligned(mat(counts = TRUE), s)
        if (any(colSums(x) <= 0)) 
            stop("Empty count library")
        keep <- rowSums(x >= p$min_count) >= p$min_samples
        if (!any(keep)) 
            stop("No count features pass declared filter")
        if (key == "translation_efficiency") {
            req(s, c("assay", "condition"))
            declared <- ctx$te_contrast
            if (is.null(declared) || !is.character(declared$control) || !is.character(declared$treatment) ||
                declared$control == declared$treatment || !setequal(s$condition, c(declared$control, declared$treatment)))
                stop("Declare exact TE control/treatment in context.te_contrast; no lexical reference guessing")
            if (!setequal(s$assay, c("Ribo", "RNA"))) stop("Exactly paired Ribo/RNA assay types required")
            s$te_interaction <- as.numeric(s$assay == "Ribo" & s$condition == declared$treatment)
            vars <- all.vars(as.formula(p$design))
            if (!all(c("unit_id", "assay", "te_interaction") %in% vars) || "condition" %in% vars)
                stop("Paired TE uses unit + assay + numeric Ribo-by-treatment interaction; condition main effect is aliased with unit")
            if (!identical(names(p$contrast), "te_interaction") || as.numeric(p$contrast[[1]]) != 1)
                stop("TE contrast must target the declared treatment-minus-control Ribo/RNA interaction")
            by_unit <- unique(s[c("unit_id", "condition")])
            if (anyDuplicated(by_unit$unit_id) || any(table(by_unit$condition) < 2)) stop("At least two independent units per TE condition required")
            keep <- rowSums(x[,s$assay == "RNA",drop=FALSE] >= p$min_count) >= p$min_samples &
                rowSums(x[,s$assay == "Ribo",drop=FALSE] >= p$min_count) >= p$min_samples
            if (!any(keep)) stop("No gene has declared count support in both RNA and Ribo")
        }
        d <- design(s)
        if (key == "differential_binding") {
            regions <- req(tab("regions"), c("feature_id", "chromosome", "start", "end"))
            if (!identical(regions$feature_id, rownames(x)) || any(regions$end <= regions$start)) 
                stop("Peak coordinates/consensus denominator invalid")
        }
        if (key == "translation_efficiency") {
            req(s, c("assay", "condition"))
            if (!all(c("Ribo", "RNA") %in% s$assay) || any(table(s$unit_id, s$assay) != 1)) 
                stop("Require exact paired RNA/Ribo libraries per independent unit")
            per <- req(tab("periodicity"), c("sample_id", "frame0_fraction", "offset_validated"))
            if (!all(s$sample_id[s$assay == "Ribo"] %in% per$sample_id) || any(!per$offset_validated) || 
                any(per$frame0_fraction <= 1/3)) 
                stop("Ribo periodicity/offset QC blocked")
            if(any(tapply(as.character(s$condition),s$unit_id,function(v)length(unique(v)))!=1))stop("Paired RNA/Ribo libraries disagree on biological condition")
        }
        y <- edgeR::DGEList(x[keep, , drop = FALSE])
        if (key == "translation_efficiency") {
            for (assay_name in c("RNA", "Ribo")) {
                select <- s$assay == assay_name
                z_norm <- edgeR::calcNormFactors(y[,select,keep.lib.sizes=FALSE])
                y$samples$norm.factors[select] <- z_norm$samples$norm.factors
            }
        } else y <- edgeR::calcNormFactors(y)
        y <- edgeR::estimateDisp(y, d, robust = TRUE)
        f <- edgeR::glmQLFit(y, d, robust = TRUE)
        test <- edgeR::glmQLFTest(f, contrast = contrast(d))
        z <- edgeR::topTags(test, n = Inf, sort.by = "none")$table
        z$feature_id <- rownames(z)
        save4(z, data.frame(feature_id = rownames(x), kept = keep), data.frame(sample_id = s$sample_id, 
            library_size = colSums(x), normalization = y$samples$norm.factors), data.frame(feature_id = rownames(y), 
            dispersion = y$tagwise.dispersion), list(features = sum(keep), samples = ncol(x), residual_df = nrow(d) - 
            ncol(d)))
    }
    else if (key %in% c("transcript_usage", "apa_usage", "isoform_switch", "exon_usage")) {
        s <- meta()
        if (!setequal(s$group, c(p$control, p$treatment))) 
            stop("Usage route requires the exact selected two-group population")
        s$group <- factor(s$group, levels = c(p$control, p$treatment))
        x <- aligned(mat(counts = TRUE), s)
        mp <- req(tab("feature_map"), c("feature_id", "gene_id"))
        if (anyDuplicated(mp$feature_id) || !all(rownames(x) %in% mp$feature_id)) 
            stop("Exact unambiguous feature-to-gene mapping required")
        mp <- mp[match(rownames(x), mp$feature_id), ]
        if(key=="apa_usage"){
            sq_pre<-req(tab("site_qc"),c("feature_id","internal_priming_fraction","terminal_coverage"))
            if(anyDuplicated(sq_pre$feature_id)||!all(rownames(x)%in%sq_pre$feature_id)||any(!is.finite(sq_pre$internal_priming_fraction))||any(!is.finite(sq_pre$terminal_coverage))||any(sq_pre$terminal_coverage<=0)||any(sq_pre$internal_priming_fraction<0|sq_pre$internal_priming_fraction>p$max_internal_priming))stop("APA input site QC failed before fitting")
        }
        d <- design(s)
        co <- contrast(d)
        if (sum(co != 0) != 1 || co[co != 0] != 1) 
            stop("This usage implementation requires one explicit positive design coefficient")
        coef <- which(co != 0)
        if (!grepl("^group", colnames(d)[coef])) stop("Usage contrast must target the selected group, not a nuisance covariate")
        keep <- rowSums(x >= p$min_count) >= p$min_samples
        if (key == "exon_usage") {
            need("DEXSeq")
            terms_exon <- attr(terms(as.formula(p$design)), "term.labels")
            if (!"group" %in% terms_exon || any(grepl(":", terms_exon, fixed = TRUE))) 
                stop("DEXSeq route requires explicit additive covariates plus group")
            full_exon_design <- as.formula(paste("~sample+exon+", paste(paste0(terms_exon, ":exon"), 
                collapse = "+")))
            reduced_exon_design <- as.formula(paste("~sample+exon", if (length(setdiff(terms_exon, "group"))) 
                paste0("+", paste(paste0(setdiff(terms_exon, "group"), ":exon"), collapse = "+"))
            else ""))
            if (!"group" %in% names(s)) 
                stop("DEXSeq requires reviewed group column")
            ds <- DEXSeq::DEXSeqDataSet(countData = x[keep, , drop = FALSE], sampleData = s, design = full_exon_design, 
                featureID = mp$feature_id[keep], groupID = mp$gene_id[keep])
            ds <- DEXSeq::estimateSizeFactors(ds)
            ds <- DEXSeq::estimateDispersions(ds)
            ds <- DEXSeq::testForDEU(ds, reducedModel = reduced_exon_design)
            ds <- DEXSeq::estimateExonFoldChanges(ds, fitExpToVar = "group")
            dxr<-DEXSeq::DEXSeqResults(ds);z <- as.data.frame(dxr)
            z$feature_id <- as.character(z$featureID)
            gene_q<-DEXSeq::perGeneQValue(dxr);gene<-data.frame(gene_id=names(gene_q),gene_q=as.numeric(gene_q),scope="native_DEXSeq_gene_level_Q")
        }
        else {
            need("DRIMSeq")
            ds <- DRIMSeq::dmDSdata(counts = data.frame(gene_id = mp$gene_id, feature_id = mp$feature_id, 
                x, check.names = FALSE), samples = s)
            ds <- DRIMSeq::dmFilter(ds, min_samps_feature_expr=p$min_samples,min_feature_expr=p$min_count,
                min_samps_gene_expr=p$min_samples,min_gene_expr=p$min_gene_count,
                min_samps_feature_prop=p$min_samples,min_feature_prop=p$min_feature_proportion)
            ds <- DRIMSeq::dmPrecision(ds, design = d)
            ds <- DRIMSeq::dmFit(ds, design = d)
            ds <- DRIMSeq::dmTest(ds, coef = coef)
            keep <- rownames(x) %in% DRIMSeq::counts(ds)$feature_id
            z <- DRIMSeq::results(ds, level = "feature")
            gene <- DRIMSeq::results(ds, level = "gene")
        }
        z <- as.data.frame(z)
        gene <- as.data.frame(gene)
        if(key!="exon_usage"){
            need("stageR")
            if(any(!is.finite(gene$pvalue))||any(!is.finite(z$pvalue)))stop("Failed/NA usage fits need explicit review before hierarchical testing")
            screen<-setNames(gene$pvalue,gene$gene_id);confirmation<-matrix(z$pvalue,ncol=1,dimnames=list(z$feature_id,"transcript"))
            txmap<-unique(z[,c("feature_id","gene_id")]);colnames(txmap)<-c("txID","geneID")
            stage<-stageR::stageRTx(pScreen=screen,pConfirmation=confirmation,pScreenAdjusted=FALSE,tx2gene=txmap)
            stage<-stageR::stageWiseAdjustment(stage,method="dtu",alpha=p$alpha_fdr)
            adjusted<-as.data.frame(stageR::getAdjustedPValues(stage,order=FALSE,onlySignificantGenes=FALSE))
            if(!all(c("txID","transcript")%in%names(adjusted)))stop("Unsupported stageR adjusted output schema")
            z$stage_q<-adjusted$transcript[match(z$feature_id,adjusted$txID)]
            write.table(adjusted,file.path(out,"hierarchical_usage_tests.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
            denom<-rowsum(x,mp$gene_id,reorder=FALSE);if(any(denom[z$gene_id,,drop=FALSE]<=0))stop("Tested gene has zero observed usage denominator; do not fill it as zero usage");usage<-x/denom[mp$gene_id,,drop=FALSE]
            z$control_usage<-rowMeans(usage[match(z$feature_id,rownames(x)),s$group==p$control,drop=FALSE])
            z$treatment_usage<-rowMeans(usage[match(z$feature_id,rownames(x)),s$group==p$treatment,drop=FALSE])
            z$delta_usage<-z$treatment_usage-z$control_usage
        }
        third <- data.frame(feature_id = rownames(x), gene_id = mp$gene_id, total_count = rowSums(x), 
            kept = keep)
        if (key == "apa_usage") {
            sq <- req(tab("site_qc"), c("feature_id", "internal_priming_fraction", "terminal_coverage"))
            if (!all(rownames(x) %in% sq$feature_id) || any(sq$terminal_coverage <= 0) || any(sq$internal_priming_fraction < 
                0 | sq$internal_priming_fraction > p$max_internal_priming)) 
                stop("APA site evidence incomplete")
            third <- merge(third, sq, by = "feature_id", all.x = TRUE)
        }
        if (key == "isoform_switch") {
            an <- req(tab("isoform_annotations"), c("feature_id", "cds_length", "domain_ids", "nmd_annotation"))
            if(anyDuplicated(an$feature_id))stop("Ambiguous isoform annotation before joining")
            if (!all(z$feature_id %in% an$feature_id)) 
                stop("Missing reviewed isoform consequences")
            z <- merge(z, an, by = "feature_id", all.x = TRUE)
            z$consequence_scope <- "annotation_predicted_not_functionally_validated"
            if(anyDuplicated(an$feature_id))stop("Ambiguous isoform annotation")
            pairs<-list();n<-0
            for(g in unique(z$gene_id)){
                up<-z[z$gene_id==g&!is.na(z$stage_q)&z$stage_q<p$alpha_fdr&z$delta_usage>=p$min_switch_delta,,drop=FALSE]
                dn<-z[z$gene_id==g&!is.na(z$stage_q)&z$stage_q<p$alpha_fdr&z$delta_usage<=-p$min_switch_delta,,drop=FALSE]
                if(nrow(up)&&nrow(dn))for(i in seq_len(nrow(up)))for(k in seq_len(nrow(dn))){n<-n+1;pairs[[n]]<-data.frame(gene_id=g,gained_isoform=up$feature_id[i],lost_isoform=dn$feature_id[k],gained_delta=up$delta_usage[i],lost_delta=dn$delta_usage[k],gained_stage_q=up$stage_q[i],lost_stage_q=dn$stage_q[k])}
            }
            switches<-if(length(pairs))do.call(rbind,pairs)else data.frame(gene_id=character(),gained_isoform=character(),lost_isoform=character(),gained_delta=double(),lost_delta=double(),gained_stage_q=double(),lost_stage_q=double())
            consequences<-switches
            domain_set<-function(v){if(is.na(v)||!nzchar(v)||v=="UNKNOWN")return(NA_character_);if(v=="NONE")return(character());unique(strsplit(v,";",fixed=TRUE)[[1]])}
            consequences$domain_gain<-character(nrow(switches));consequences$domain_loss<-character(nrow(switches));consequences$CDS_length_change<-double(nrow(switches));consequences$NMD_change<-character(nrow(switches))
            for(i in seq_len(nrow(switches))){a<-an[match(switches$gained_isoform[i],an$feature_id),];b<-an[match(switches$lost_isoform[i],an$feature_id),];aa<-domain_set(a$domain_ids);bb<-domain_set(b$domain_ids);consequences$domain_gain[i]<-if(anyNA(c(aa,bb)))"UNASSESSED"else paste(setdiff(aa,bb),collapse=";");consequences$domain_loss[i]<-if(anyNA(c(aa,bb)))"UNASSESSED"else paste(setdiff(bb,aa),collapse=";");consequences$CDS_length_change[i]<-a$cds_length-b$cds_length;consequences$NMD_change[i]<-paste(b$nmd_annotation,a$nmd_annotation,sep=" -> ")}
            write.table(z,file.path(out,"complete_isoform_DTU_family.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
        }
        write.table(data.frame(sample_id = s$sample_id, d, check.names = FALSE), file.path(out, "usage_design.tsv"), 
            sep = "\t", quote = FALSE, row.names = FALSE)
        if (key != "exon_usage") {
            prop <- DRIMSeq::proportions(ds)
            write.table(prop, file.path(out, "fitted_feature_proportions.tsv"), sep = "\t", quote = FALSE, 
                row.names = FALSE)
        }
        if (key == "apa_usage") {
            save4(z, merge(mp, sq, by = "feature_id", all.x = TRUE), third, gene, list(tested_features = nrow(z), 
                tested_genes = nrow(gene), independent_units = nrow(s)))
        }
        else if (key == "isoform_switch") {
            save4(switches, consequences, mp, data.frame(feature_id = z$feature_id, stage_q=z$stage_q, scope = "annotation_predicted_not_experimental_consequence"), 
                list(tested_features = nrow(z), tested_genes = nrow(gene), independent_units = nrow(s)))
        }
        else {
            if(key=="transcript_usage")gene<-adjusted
            if(key=="exon_usage")save4(z,third,gene,data.frame(sample_id=s$sample_id,library_count=colSums(x),design_rank=qr(d)$rank),list(tested_features=nrow(z),tested_genes=nrow(gene),independent_units=nrow(s)))
            else save4(z, mp, third, gene, list(tested_features = nrow(z), tested_genes = nrow(gene), independent_units = nrow(s)))
        }
    }
    else if (key == "fine_mapping") {
        need("susieR")
        z <- req(tab("summary"), c("variant_id", "beta", "se", "effect_allele", "other_allele"))
        ld <- mat("ld")
        ax <- req(tab("ld_variants"), c("variant_id", "effect_allele", "other_allele"))
        if (!identical(z$variant_id, ax$variant_id) || !identical(z$effect_allele, ax$effect_allele) || 
            !identical(z$other_allele, ax$other_allele) || !identical(rownames(ld), z$variant_id) || 
            !identical(colnames(ld), z$variant_id)) 
            stop("Exact variant/allele LD alignment required")
        eig <- eigen(ld, symmetric = TRUE, only.values = TRUE)$values
        if (max(abs(ld - t(ld))) > 1e-06 || max(abs(diag(ld) - 1)) > 1e-05 || min(eig) < -1e-06 || any(z$se <= 
            0)) 
            stop("Invalid LD/SE")
        fit <- susieR::susie_rss(bhat = z$beta, shat = z$se, R = ld, n = p$sample_size, L = p$L, coverage = p$coverage, 
            min_abs_corr = p$min_abs_corr)
        cs <- fit$sets$cs
        ct <- if (length(cs)) 
            do.call(rbind, lapply(names(cs), function(id) data.frame(set = id, variant_id = z$variant_id[cs[[id]]])))
        else data.frame(set = character(), variant_id = character())
        save4(data.frame(z, posterior_inclusion_probability = fit$pip), ct, data.frame(min_eigenvalue = min(eig), 
            max_asymmetry = max(abs(ld - t(ld))), min_diagonal = min(diag(ld))), data.frame(iteration = seq_along(fit$elbo), 
            elbo = fit$elbo), list(variants = nrow(z), converged = as.integer(fit$converged), min_ld_eigenvalue = min(eig)))
    }
    else if (key == "colocalization") {
        need("coloc")
        a <- req(tab("trait1"), c("variant_id", "beta", "se", "maf", "effect_allele", "other_allele"))
        b <- req(tab("trait2"), names(a))
        if(anyDuplicated(a$variant_id)||anyDuplicated(b$variant_id)||any(!is.finite(a$beta))||any(!is.finite(b$beta))||any(a$maf<=0|a$maf>0.5)||any(b$maf<=0|b$maf>0.5))stop("Coloc variant IDs, effects or MAF invalid")
        merged <- merge(a, b, by = "variant_id", suffixes = c("_1", "_2"))
        if(nrow(merged)/nrow(a)<p$min_shared_fraction || nrow(merged)/nrow(b)<p$min_shared_fraction)stop("Coloc shared variant coverage below prespecified fraction")
        if (nrow(merged) < 50 || any(merged$effect_allele_1 != merged$effect_allele_2 | merged$other_allele_1 != 
            merged$other_allele_2) || any(merged$se_1 <= 0 | merged$se_2 <= 0)) 
            stop("Too few shared or unharmonized variants")
        mk <- function(suffix, type, n) {
            r <- list(beta = merged[[paste0("beta_", suffix)]], varbeta = merged[[paste0("se_", suffix)]]^2, 
                snp = merged$variant_id, MAF = merged[[paste0("maf_", suffix)]], N = n, type = type)
            if (type == "cc") {
                s <- p[[paste0("case_fraction", suffix)]]
                if (is.null(s) || s <= 0 || s >= 1) 
                  stop("Case fraction required")
                r$s <- s
            }else{sdY<-p[[paste0("sdY",suffix)]];if(is.null(sdY)||!is.finite(sdY)||sdY<=0)stop("Quantitative coloc needs phenotype SD on the exact effect scale");r$sdY<-sdY}
            r
        }
        d1<-mk("1",p$trait1_type,p$n1);d2<-mk("2",p$trait2_type,p$n2)
        if(p$coloc_mode=="ABF"){
            fit<-coloc::coloc.abf(d1,d2,p1=p$p1,p2=p$p2,p12=p$p12);which_h<-grep("^PP\\.H[0-4]",names(fit$summary));hypotheses<-data.frame(signal_pair="single_causal_model",hypothesis=names(fit$summary)[which_h],value=as.numeric(fit$summary[which_h]));pair_results<-fit$results
        }else if(p$coloc_mode=="SuSiE"){
            getLD<-function(name,map,suffix){
                ld<-mat(name);mapping<-req(tab(map),c("variant_id","effect_allele","other_allele"));ids<-merged$variant_id
                if(anyDuplicated(mapping$variant_id)||!all(ids%in%rownames(ld))||!setequal(rownames(ld),colnames(ld))||!all(ids%in%mapping$variant_id))stop("Coloc LD/variant identity mismatch")
                z<-mapping[match(ids,mapping$variant_id),];if(any(z$effect_allele!=merged[[paste0("effect_allele_",suffix)]])||any(z$other_allele!=merged[[paste0("other_allele_",suffix)]]))stop("Signed LD allele orientation differs from harmonized effect alleles")
                ld<-ld[ids,ids,drop=FALSE];if(max(abs(ld-t(ld)))>1e-7||max(abs(diag(ld)-1))>1e-6||min(eigen(ld,symmetric=TRUE,only.values=TRUE)$values)< -1e-6)stop("Invalid signed LD correlation matrix");ld
            }
            d1$LD<-getLD("ld1","ld1_variants","1");d2$LD<-getLD("ld2","ld2_variants","2")
            s1<-coloc::runsusie(d1,L=p$L,maxit=p$max_iter,repeat_until_convergence=FALSE);s2<-coloc::runsusie(d2,L=p$L,maxit=p$max_iter,repeat_until_convergence=FALSE)
            if(!isTRUE(s1$converged)||!isTRUE(s2$converged))stop("Coloc SuSiE did not converge")
            fit<-coloc::coloc.susie(s1,s2,p1=p$p1,p2=p$p2,p12=p$p12);pairs<-as.data.frame(fit$summary)
            if(!nrow(pairs))stop("No credible-set pairs available; colocalization is unassessed, not a negative result")
            cols<-grep("^PP\\.H[0-4]",names(pairs),value=TRUE);if(length(cols)!=5)stop("Unexpected native coloc.susie posterior schema")
            hypotheses<-do.call(rbind,lapply(seq_len(nrow(pairs)),function(k)data.frame(signal_pair=paste0("pair_",k),hypothesis=cols,value=as.numeric(unlist(pairs[k,cols],use.names=FALSE)))));pair_results<-pairs
            saveRDS(list(trait1=s1,trait2=s2,coloc=fit),file.path(out,"native_coloc_susie.rds"))
        }else stop("Explicit ABF or SuSiE colocalization mode required")
        sums<-aggregate(value~signal_pair,hypotheses,sum);if(any(abs(sums$value-1)>1e-6)||any(!is.finite(hypotheses$value))||any(hypotheses$value<0|hypotheses$value>1))stop("Coloc hypothesis probabilities invalid")
        save4(hypotheses,merged,pair_results,data.frame(trait=c("1","2"),all_variants=c(nrow(a),nrow(b)),shared=nrow(merged),mode=p$coloc_mode),list(shared_variants=nrow(merged),trait1_coverage=nrow(merged)/nrow(a),trait2_coverage=nrow(merged)/nrow(b),signal_pairs=nrow(sums)))
    }
    else if (key == "two_sample_mr") {
        need("TwoSampleMR")
        a <- tab("exposure")
        b <- tab("outcome")
        cl <- req(tab("clump_evidence"), c("SNP", "ld_clumped", "reference_version"))
        if (!all(cl$ld_clumped) || anyDuplicated(cl$SNP)) 
            stop("Require independently reviewed offline LD clumping")
        req(a,c("SNP","beta","se","effect_allele","other_allele","eaf"));req(b,c("SNP","beta","se","effect_allele","other_allele","eaf"))
        if(anyDuplicated(a$SNP)||anyDuplicated(b$SNP)||any(a$se<=0)||any(b$se<=0)||any(!is.finite(a$beta))||any(!is.finite(b$beta)))stop("Invalid MR summary statistics")
        original_instruments<-a
        if(!setequal(a$SNP,cl$SNP))stop("Exposure instrument set and offline clump evidence differ")
        a <- a[a$SNP %in% cl$SNP, ]
        if (any(a$beta^2/a$se^2 < p$f_threshold)) 
            stop("Weak instruments remain")
        ea <- TwoSampleMR::format_data(a, type = "exposure")
        ob <- TwoSampleMR::format_data(b, type = "outcome")
        h <- TwoSampleMR::harmonise_data(ea, ob, action = p$action)
        if(anyDuplicated(h$SNP))stop("Unexpected duplicated harmonized instrument; do not multiply audit rows")
        audit<-merge(data.frame(SNP=original_instruments$SNP,F_stat=original_instruments$beta^2/original_instruments$se^2,outcome_available=original_instruments$SNP%in%b$SNP),h,by="SNP",all.x=TRUE)
        write.table(audit,file.path(out,"all_instrument_audit.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
        if (sum(h$mr_keep) < 3) 
            stop("Too few harmonised instruments")
        res <- TwoSampleMR::mr(h)
        het <- TwoSampleMR::mr_heterogeneity(h)
        pleio <- TwoSampleMR::mr_pleiotropy_test(h)
        if(anyDuplicated(pleio[,c('id.exposure','id.outcome','exposure','outcome'),drop=FALSE]))stop("Ambiguous pleiotropy diagnostic identity")
        loo <- TwoSampleMR::mr_leaveoneout(h)
        save4(res, h, merge(het,pleio,by=c('id.exposure','id.outcome','exposure','outcome'),all=TRUE), loo, list(instruments = sum(h$mr_keep), removed = sum(!h$mr_keep), 
            min_F = min(a$beta^2/a$se^2)))
    }
    else if (key == "rare_variant_burden") {
        need("SKAT")
        s <- meta()
        g <- t(aligned(mat("genotype"), s))
        if (any(g < 0 | g > 2) || any(g != round(g))) 
            stop("Genotype must be selected diploid 0/1/2 without missingness")
        masks <- req(tab("variant_masks"), c("variant_id", "mask"))
        if (!all(masks$variant_id %in% colnames(g))) 
            stop("Variant masks mismatch")
        if (any(s$relatedness_group[!is.na(s$relatedness_group)] != "unrelated")) 
            stop("Use a relatedness-aware backend for related units")
        ra <- req(tab("relatedness_audit"), c("unit_id", "unrelated", "reviewed"))
        if (!setequal(ra$unit_id, s$unit_id) || !all(ra$unrelated) || !all(ra$reviewed)) 
            stop("SKAT independent-unit relatedness QC failed")
        if (!grepl("^[A-Za-z0-9_ +*:~.-]+$", p$null_formula)) 
            stop("Unsafe null formula")
        null <- SKAT::SKAT_Null_Model(as.formula(p$null_formula), data = s, out_type = p$outcome_type, 
            n.Resampling = p$permutations)
        if(anyDuplicated(masks[,c("variant_id","mask")]))stop("Duplicate variant in a burden mask")
        if(any(colMeans(g)/2>0.5))stop("This rare-variant route requires actual minor-allele dosages, not arbitrary ALT dosages")
        sets <- lapply(split(masks$variant_id, masks$mask),unique)
        calibration <- list()
        r <- do.call(rbind, lapply(names(sets), function(id) {
            z <- g[, sets[[id]], drop = FALSE]
            mac <- pmin(colSums(z), 2 * nrow(z) - colSums(z))
            z <- z[, mac>=p$min_mac & mac/(2*nrow(z))<=p$max_maf, drop=FALSE]
            if (!ncol(z)) 
                return(data.frame(mask = id, p = NA_real_, variants = 0, carriers = 0))
            if(p$skat_test=="SKATO")v<-SKAT::SKAT(z,null,method="optimal.adj")
            else {if(!p$skat_test%in%c("SKAT","burden"))stop("Unknown rare-variant test family");v<-SKAT::SKAT(z,null,method=p$skat_method,r.corr=ifelse(p$skat_test=="burden",1,0))}
            if(p$skat_test!="SKATO" && p$skat_method=="davies" && !is.null(v$param$Is_Converged) && v$param$Is_Converged!=1)stop("Davies did not converge; fallback must be chosen and reviewed explicitly")
            if (is.null(v$p.value.resampling)) 
                stop("Actual SKAT null calibration missing")
            calibration[[id]] <<- data.frame(mask = id, iteration = seq_along(v$p.value.resampling), 
                null_p = as.numeric(v$p.value.resampling))
            data.frame(mask = id, p = v$p.value, variants = ncol(z), carriers = sum(rowSums(z) > 0))
        }))
        r$q <- p.adjust(r$p, "BH")
        calibration_table <- do.call(rbind, calibration)
        if (is.null(calibration_table) || !nrow(calibration_table)) stop("No mask has actual null calibration")
        calibration_table$nominal_alpha <- p$calibration_alpha
        save4(r, masks, data.frame(variant_id = colnames(g), minor_allele_count = pmin(colSums(g), 2 * 
            nrow(g) - colSums(g))), calibration_table, list(units = nrow(g), tested_masks = sum(r$variants > 
            0), untestable_masks = sum(r$variants == 0), empirical_null_rejection = mean(calibration_table$null_p < 
            p$calibration_alpha)))
    }
    else if (key == "multiomics_mediation") {
        need("mediation")
        s <- req(tab("mediation_data"), c("unit_id", p$exposure, p$mediator, p$outcome, unlist(p$covariates)))
        if (anyDuplicated(s$unit_id) || anyNA(s)) 
            stop("Independent complete-case units required; missingness selection must be reviewed")
        safe <- c(p$exposure, p$mediator, p$outcome, unlist(p$covariates))
        if (any(!grepl("^[A-Za-z][A-Za-z0-9_]*$", safe))) 
            stop("Unsafe model columns")
        fm <- reformulate(c(p$exposure, unlist(p$covariates)), response = p$mediator)
        fy <- reformulate(c(p$exposure, p$mediator, unlist(p$covariates)), response = p$outcome)
        if(!is.numeric(s[[p$mediator]])||!is.numeric(s[[p$outcome]])||length(unique(s[[p$outcome]]))<5)stop("This mediation branch uses continuous mediator/outcome linear models, not binary-outcome or survival mediation")
        if(!all(c(p$treat_value,p$control_value)%in%range(s[[p$exposure]])) && (p$treat_value>max(s[[p$exposure]])||p$treat_value<min(s[[p$exposure]])||p$control_value>max(s[[p$exposure]])||p$control_value<min(s[[p$exposure]])))stop("Mediation contrast extrapolates outside observed exposure support")
        m <- lm(fm, s);y <- lm(fy, s)
        if(m$rank!=ncol(model.matrix(m))||y$rank!=ncol(model.matrix(y))||min(m$df.residual,y$df.residual)<3)stop("Mediation design is singular or lacks residual degrees of freedom")
        fit <- mediation::mediate(m, y, treat = p$exposure, mediator = p$mediator, sims = p$simulations, 
            boot = TRUE, treat.value = p$treat_value, control.value = p$control_value)
        sen <- mediation::medsens(fit, rho.by = 0.1, effect.type = "indirect")
        save4(data.frame(exposure = p$exposure, mediator = p$mediator, outcome = p$outcome, treat = p$treat_value, 
            control = p$control_value), data.frame(estimand = c("ACME", "ADE", "total"), estimate = c(fit$d0, 
            fit$z0, fit$tau.coef), ci_lower = c(fit$d0.ci[1], fit$z0.ci[1], fit$tau.ci[1]), ci_upper = c(fit$d0.ci[2], 
            fit$z0.ci[2], fit$tau.ci[2])), data.frame(unit_id = s$unit_id, mediator_residual = residuals(m), 
            outcome_residual = residuals(y)), data.frame(rho = sen$rho, ACME = sen$d0), list(independent_units = nrow(s), 
            residual_df_m = m$df.residual, residual_df_y = y$df.residual))
    }
    else if (key == "bulk_deconvolution") {
        need("MuSiC")
        need("SingleCellExperiment")
        x <- mat()
        s <- meta()
        x <- aligned(x, s)
        ref <- readRDS(I$reference_sce)
        if (!inherits(ref, "SingleCellExperiment")) 
            stop("Expected reviewed reference SingleCellExperiment")
        cd <- as.data.frame(SummarizedExperiment::colData(ref))
        req(cd, c(p$celltype_column, p$donor_column))
        keep_cells <- !cd[[p$donor_column]] %in% unlist(p$reference_exclude_donors)
        if (any(table(cd[[p$celltype_column]][keep_cells]) < p$min_cells)) 
            stop("Reference celltype coverage below threshold")
        cross_reference<-table(cd[[p$donor_column]][keep_cells],cd[[p$celltype_column]][keep_cells])
        if(any(colSums(cross_reference>0)<p$min_reference_donors))stop("Reference celltype occurs in too few independent donors")
        ref <- ref[, keep_cells]
        cd <- cd[keep_cells, , drop = FALSE]
        if (length(unique(cd[[p$donor_column]])) < 3) 
            stop("Need independent reference donors")
        fit <- MuSiC::music_prop(bulk.mtx = x, sc.sce = ref, clusters = p$celltype_column, samples = p$donor_column, 
            verbose = FALSE)
        z <- fit$Est.prop.weighted
        if (any(z < 0) || any(abs(rowSums(z) - 1) > 0.01)) 
            stop("Invalid inferred fractions")
        meanref <- vapply(colnames(z), function(ct) rowMeans(SummarizedExperiment::assay(ref, "counts")[, 
            cd[[p$celltype_column]] == ct, drop = FALSE]), numeric(nrow(ref)))
        rownames(meanref)<-rownames(ref)
        g <- intersect(rownames(x), rownames(meanref))
        if(length(g)<p$min_reference_genes)stop("Insufficient shared reference gene coverage")
        saveRDS(fit,file.path(out,"music_full_native_fit.rds"))
        pred <- meanref[g, , drop = FALSE] %*% t(z)
        save4(data.frame(sample_id = rownames(z), z), data.frame(feature_id = rownames(x), in_reference = rownames(x) %in% 
            g), data.frame(sample_id = colnames(x), proxy_reconstruction_correlation = vapply(seq_len(ncol(x)), 
            function(i) cor(x[g, i], pred[, i]), numeric(1))), data.frame(celltype=colnames(cross_reference),reference_donors=colSums(cross_reference>0),n_cells=colSums(cross_reference)), list(reference_donors = length(unique(cd[[p$donor_column]])), 
            shared_genes = length(g), samples = ncol(x)))
    }
    else if (key == "spatial_deconvolution") {
        need("spacexr")
        counts <- mat(counts = TRUE)
        coords <- req(tab("coordinates"), c("spot_id", "x", "y", "section_id", "unit_id"))
        if(anyDuplicated(coords$spot_id)||anyNA(coords$spot_id)||any(!nzchar(coords$spot_id))||any(!is.finite(as.matrix(coords[,c('x','y')]))))stop("Unique finite spatial coordinate axes required")
        if (length(unique(coords$section_id)) != 1) 
            stop("RCTD invocation is one section; replicate across independent sections")
        if (!setequal(coords$spot_id, colnames(counts))) 
            stop("Spatial coordinates mismatch")
        coords <- coords[match(colnames(counts), coords$spot_id), ]
        ref <- mat("reference_counts", TRUE)
        md <- req(tab("reference_metadata"), c("cell_id", p$celltype_column, p$donor_column))
        md <- md[match(colnames(ref), md$cell_id), ]
        if (anyNA(md) || length(unique(md[[p$donor_column]])) < 2) 
            stop("Reference donor/cell mapping invalid")
        hist <- req(tab("histology"), c("spot_id", "reviewed", "tissue_present"))
        if (!all(coords$spot_id %in% hist$spot_id) || !all(hist$reviewed) || !all(hist$tissue_present)) 
            stop("Actual reviewed histology required")
        if(anyDuplicated(md$cell_id)||anyDuplicated(hist$spot_id))stop("Duplicate reference/histology axes")
        keep_ref<-!md[[p$donor_column]]%in%unlist(p$reference_exclude_donors);ref<-ref[,keep_ref,drop=FALSE];md<-md[keep_ref,,drop=FALSE]
        if(length(unique(md[[p$donor_column]]))<2)stop("Too few remaining reference donors")
        types<-factor(md[[p$celltype_column]]);names(types)<-colnames(ref)
        if(p$rctd_api=="bioconductor"){
            need("SpatialExperiment");need("SummarizedExperiment")
            spatial<-SpatialExperiment::SpatialExperiment(assays=list(counts=counts),spatialCoords=as.matrix(coords[,c("x","y")]))
            reference<-SummarizedExperiment::SummarizedExperiment(assays=list(counts=ref),colData=md)
            rownames(SummarizedExperiment::colData(reference))<-colnames(ref)
            prepared<-spacexr::createRctd(spatial,reference,cell_type_col=p$celltype_column)
            result<-spacexr::runRctd(prepared,rctd_mode=p$doublet_mode,max_cores=1)
            w<-as.data.frame(t(SummarizedExperiment::assay(result,"weights")))
            classification<-as.data.frame(SummarizedExperiment::colData(result));classification$spot_id<-rownames(classification)
        }else if(p$rctd_api=="legacy"){
            if(p$doublet_mode!="full")stop("Legacy adapter supports full weights only; choose the Bioconductor branch for doublet/multi classifications")
            reference<-spacexr::Reference(ref,types,colSums(ref))
            spatial<-spacexr::SpatialRNA(data.frame(x=coords$x,y=coords$y,row.names=coords$spot_id),counts,colSums(counts))
            prepared<-spacexr::create.RCTD(spatial,reference,max_cores=1)
            result<-spacexr::run.RCTD(prepared,doublet_mode="full")
            raw<-as.matrix(result@results$weights);w<-as.data.frame(raw/rowSums(raw));classification<-data.frame(spot_id=rownames(w),native_class="full_continuous_weights")
        }else stop("Select exact RCTD API")
        if(anyDuplicated(rownames(w))||anyDuplicated(classification$spot_id)||!all(rownames(w)%in%colnames(counts))||!all(classification$spot_id%in%colnames(counts))||!all(colnames(w)%in%levels(types)))stop("RCTD native identity or cell-type axes disagree with inputs")
        if(any(!is.finite(as.matrix(w)))||any(w<0))stop("Invalid RCTD inferred weights")
        sums<-rowSums(w);if(any(abs(sums-1)>1e-5 & sums!=0))stop("RCTD weights are neither normalized nor explicitly rejected")
        saveRDS(result,file.path(out,"rctd_native_result.rds"))
        input_order<-match(colnames(counts),rownames(w));native<-data.frame(spot_id=colnames(counts),returned_in_weights=!is.na(input_order),weight_sum=sums[input_order],assignment_state=ifelse(is.na(input_order),"UNASSESSED_NATIVE_FILTERED",ifelse(sums[input_order]==0,"REJECTED","ESTIMATED")),uncertainty_scope="native_classification_and_reference_sensitivity_not_posterior_CI")
        save4(data.frame(spot_id=rownames(w),w),data.frame(gene=intersect(rownames(counts),rownames(ref)),reference_covered=TRUE),merge(native,classification,by="spot_id",all=TRUE),hist,
          list(spots=ncol(counts),returned_spots=nrow(w),unassessed_filtered_spots=sum(is.na(input_order)),rejected_spots=sum(sums==0),reference_cells=ncol(ref),reference_donors=length(unique(md[[p$donor_column]]))))
    }
    else if (key == "singlecell_abundance") {
        need("miloR")
        s <- meta()
        sce <- readRDS(I$singlecell_sce)
        cd <- as.data.frame(SummarizedExperiment::colData(sce))
        req(cd, c("sample_id"))
        if (!all(cd$sample_id %in% s$sample_id)) 
            stop("Cell/sample mapping incomplete")
        m <- miloR::Milo(sce)
        m <- miloR::buildGraph(m, k = p$k, d = p$d)
        m <- miloR::makeNhoods(m, prop = p$prop, k = p$k, d = p$d, refined = TRUE)
        m <- miloR::countCells(m, meta.data = cd, samples = "sample_id")
        m <- miloR::calcNhoodDistance(m, d = p$d)
        d<-design(s)
        native_samples<-colnames(miloR::nhoodCounts(m));if(!setequal(native_samples,s$sample_id))stop("Milo independent sample count mismatch")
        s<-s[native_samples,,drop=FALSE]
        if(!grepl("^[A-Za-z0-9_ .+*:-]+$",p$model_contrast))stop("Unsafe neighborhood contrast")
        res <- miloR::testNhoods(m, design = as.formula(p$design), design.df = s, model.contrasts = p$model_contrast)
        res$neighborhood<-rownames(res)
        nc <- as.matrix(miloR::nhoodCounts(m))
        save4(res, nc, data.frame(neighborhood = seq_len(nrow(res)), spatial_FDR = res$SpatialFDR), data.frame(sample_id = s$sample_id, 
            cells = as.integer(table(factor(cd$sample_id, levels = s$sample_id)))), list(independent_units = nrow(s), 
            neighborhoods = nrow(res), cells = ncol(sce)))
    }
    else if (key == "trajectory_topology") {
        need("slingshot")
        sce <- readRDS(I$singlecell_sce)
        root <- req(tab("root_evidence"), c("cluster", "evidence", "reviewed"))
        if (!p$start_cluster %in% root$cluster || !all(root$reviewed)) 
            stop("Root evidence not reviewed")
        sce <- slingshot::slingshot(sce, clusterLabels = p$cluster_key, reducedDim = p$reduced_dim, start.clus = p$start_cluster)
        pt <- slingshot::slingPseudotime(sce)
        cw <- slingshot::slingCurveWeights(sce)
        lineages <- slingshot::slingLineages(sce)
        edge_keys<-function(v){unique(unlist(lapply(v,function(path){if(length(path)<2)return(character());paste(head(path,-1),tail(path,-1),sep=" -> ")})))}
        original_edges<-edge_keys(lineages)
        edge <- do.call(rbind, lapply(seq_along(lineages), function(i) data.frame(lineage = i, position = seq_along(lineages[[i]]), 
            cluster = lineages[[i]])))
        cd <- as.data.frame(SummarizedExperiment::colData(sce))
        req(cd, c("unit_id"))
        donors <- unique(cd$unit_id)
        if (length(donors) < 4) 
            stop("Trajectory topology stability needs >=4 independent donors")
        write.table(data.frame(cell_id = rownames(cw), cw), file.path(out, "curve_weights.tsv"), sep = "\t", 
            quote = FALSE, row.names = FALSE)
        stability <- list()
        for (it in seq_len(p$donor_resamples)) {
            selected <- sample(donors, max(3, floor(0.8 * length(donors))), replace = FALSE)
            ss <- sce[, cd$unit_id %in% selected]
            if (!p$start_cluster %in% SummarizedExperiment::colData(ss)[[p$cluster_key]]) 
                stop("Root absent in a donor resample")
            ss <- slingshot::slingshot(ss, clusterLabels = p$cluster_key, reducedDim = p$reduced_dim, 
                start.clus = p$start_cluster)
            ll <- slingshot::slingLineages(ss)
            other_edges<-edge_keys(ll);union_edges<-union(original_edges,other_edges);edge_Jaccard<-if(length(union_edges))length(intersect(original_edges,other_edges))/length(union_edges)else 1
            stability[[it]] <- data.frame(iteration = it, donors = length(selected), lineages = length(ll),edge_Jaccard=edge_Jaccard, 
                root_retained = as.integer(all(vapply(ll, function(v) v[1] == p$start_cluster, logical(1)))))
        }
        save4(edge, pt, root, do.call(rbind, stability), list(cells = nrow(pt), lineages = ncol(pt), 
            independent_donors = length(donors), assigned = sum(rowSums(is.finite(pt)) > 0)))
    }
    else if (key == "trajectory_dynamics") {
        need("tradeSeq")
        x <- mat(counts = TRUE)
        pt <- as.matrix(read.delim(I$pseudotime,row.names=1,check.names=FALSE,na.strings=c("NA","NaN")))
        w <- mat("cell_weights")
        md <- req(tab("cell_metadata"), c("cell_id", "unit_id"))
        if (!identical(colnames(x), rownames(pt)) || !identical(rownames(pt), rownames(w)) || !identical(rownames(pt), 
            md$cell_id)) 
            stop("Trajectory cell axes mismatch")
        if(!identical(dim(pt),dim(w))||!identical(colnames(pt),colnames(w))||any(!is.finite(w))||any(w<0)||any(rowSums(w)<=0))stop("Trajectory lineage weights invalid")
        if(any(!is.finite(pt)&w>0))stop("Missing pseudotime on an active lineage")
        pt[!is.finite(pt)&w==0]<-0
        fit <- tradeSeq::fitGAM(counts = x, pseudotime = pt, cellWeights = w, nknots = p$nknots, verbose = FALSE)
        z <- switch(p$test_family, association = tradeSeq::associationTest(fit), pattern = tradeSeq::patternTest(fit), 
            endpoint = tradeSeq::diffEndTest(fit), stop("Choose exact supported test family"))
        z$feature_id <- rownames(z)
        for (k in grep("pvalue", names(z), value = TRUE)) z[[paste0(k, "_BH")]] <- p.adjust(z[[k]], "BH")
        conv <- SummarizedExperiment::rowData(fit)$tradeSeq$converged
        curve_list<-lapply(rownames(x)[which(conv)],function(g){v<-tradeSeq::predictSmooth(fit,gene=g,nPoints=p$curve_points,tidy=TRUE);v$feature_id<-g;v})
        curves<-do.call(rbind,curve_list);if(is.null(curves))stop("No converged trajectory curves")
        if(any(!conv|is.na(conv)))stop("Trajectory contains unassessed/nonconverged genes; preserve failed fits and do not report global success")
        save4(z, curves, data.frame(feature_id = rownames(x), 
            converged = conv), data.frame(test = p$test_family, scope = "cell_conditional_not_donor_population"), 
            list(genes = nrow(x), cells = ncol(x), donors = length(unique(md$unit_id)), converged_genes = sum(conv,na.rm=TRUE),converged_fraction=mean(conv,na.rm=TRUE)))
    }
    else if (key == "microbe_diversity") {
        need("vegan")
        need("permute")
        s <- meta()
        x <- t(aligned(mat(counts = TRUE), s))
        if (any(rowSums(x) == 0)) 
            stop("Empty microbial library")
        alpha <- data.frame(sample_id = s$sample_id, unit_id = s$unit_id, shannon = vegan::diversity(x), 
            simpson = vegan::diversity(x, "simpson"), observed = rowSums(x > 0))
        relative<-x/rowSums(x)
        dist <- vegan::vegdist(relative, method = p$distance)
        grp <- factor(s[[p$group]])
        if (any(table(grp) < 3)) 
            stop("Too few independent units")
        ctrl <- permute::how(nperm = p$permutations)
        per <- vegan::adonis2(dist ~ grp, permutations = ctrl)
        bd <- vegan::betadisper(dist, grp)
        dt <- vegan::permutest(bd, permutations = ctrl)
        save4(alpha, as.matrix(dist), data.frame(term = rownames(per), as.data.frame(per)), data.frame(term = rownames(dt$tab), 
            as.data.frame(dt$tab)), list(units = nrow(s), min_library = min(rowSums(x)), dispersion_F = dt$tab$F[1]))
    }
    else if (key == "microbe_differential") {
        need("ANCOMBC")
        need("phyloseq")
        if (!grepl("^[A-Za-z0-9_ +*:.-]+$", p$formula)) 
            stop("Unsafe ANCOMBC2 formula")
        s <- meta()
        x <- aligned(mat(counts = TRUE), s)
        if (any(colSums(x) <= 0)) 
            stop("Empty microbe samples")
        otu <- phyloseq::otu_table(x, taxa_are_rows = TRUE)
        ps <- phyloseq::phyloseq(otu, phyloseq::sample_data(s))
        fit <- ANCOMBC::ancombc2(data = ps, fix_formula = p$formula, group = p$group, prv_cut = p$prv_cut, 
            lib_cut = p$lib_cut, struc_zero = TRUE, neg_lb = TRUE, global = TRUE, pairwise = TRUE, verbose = FALSE)
        zeros<-as.data.frame(fit$zero_ind);if(!"taxon"%in%names(zeros))zeros$taxon<-rownames(zeros)
        save4(as.data.frame(fit$res), zeros, data.frame(feature_id = rownames(x), 
            prevalence = rowMeans(x > 0), total = rowSums(x)), as.data.frame(fit$res_global), list(taxa = nrow(x), 
            units = nrow(s), min_library = min(colSums(x))))
    }
    else if (key == "microbe_network") {
        need("SpiecEasi")
        s <- meta()
        x <- t(aligned(mat(counts = TRUE), s))
        if (any(colSums(x) == 0)) 
            stop("Zero-only taxa must be explicitly filtered upstream")
        fit <- SpiecEasi::spiec.easi(x, method = "mb", nlambda = p$nlambda, lambda.min.ratio = p$lambda_min_ratio, 
            sel.criterion = "stars", pulsar.params = list(rep.num = p$stars_reps))
        adj <- as.matrix(SpiecEasi::getRefit(fit))
        idx <- which(upper.tri(adj) & adj != 0, arr.ind = TRUE)
        edges <- data.frame(source = colnames(x)[idx[, 1]], target = colnames(x)[idx[, 2]])
        edge_stability<-as.matrix(SpiecEasi::getOptMerge(fit));beta <- as.matrix(SpiecEasi::getOptBeta(fit))
        selection<-data.frame(selected_index=SpiecEasi::getOptInd(fit),selected_lambda=SpiecEasi::getOptLambda(fit),StARS_instability=SpiecEasi::getStability(fit))
        if(selection$selected_index%in%c(1,p$nlambda))stop("SPIEC-EASI selection is at lambda path boundary; expand/review path before scientific acceptance")
        idx_all<-which(upper.tri(edge_stability),arr.ind=TRUE);stability_table<-data.frame(source=colnames(x)[idx_all[,1]],target=colnames(x)[idx_all[,2]],edge_selection_frequency=edge_stability[idx_all])
        write.table(data.frame(feature_id=rownames(beta),beta,check.names=FALSE),file.path(out,"native_neighborhood_coefficients.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
        nulls <- lapply(seq_len(p$null_permutations), function(it) {
            xx <- apply(x, 2, sample)
            ff <- SpiecEasi::spiec.easi(xx, method = "mb", nlambda = p$nlambda, lambda.min.ratio = p$lambda_min_ratio, 
                sel.criterion = "stars", pulsar.params = list(rep.num = p$stars_reps))
            aa <- as.matrix(SpiecEasi::getRefit(ff))
            data.frame(iteration = it, edges = sum(aa[upper.tri(aa)] != 0))
        })
        save4(edges, selection, stability_table, do.call(rbind, 
            nulls), list(units = nrow(x), taxa = ncol(x), selected_edges = nrow(edges)))
    }
    else if (key == "lipid_class_enrichment") {
        need("fgsea")
        z <- req(tab("feature_stats"), c("feature_id", "statistic"))
        mp <- req(tab("lipid_annotations"), c("feature_id", "class", "identity_ambiguous"))
        if (anyDuplicated(z$feature_id) || any(mp$identity_ambiguous)) 
            stop("Unresolved lipid identity or duplicate statistics")
        sets <- lapply(split(mp$feature_id, mp$class), unique)
        ranks <- setNames(z$statistic, z$feature_id)
        r <- as.data.frame(fgsea::fgseaMultilevel(sets, ranks, minSize = p$min_set_size, maxSize = p$max_set_size))
        r$leadingEdge <- vapply(r$leadingEdge, paste, collapse = ";", character(1))
        save4(r, z, mp, cover(sets, z$feature_id), list(lipids = nrow(z), classes = nrow(r)))
    }
    else if (key == "ligand_target_links") {
        need("nichenetr")
        prior <- mat("target_prior")
        de <- req(tab("receiver_de"), c("feature_id", "logFC", "q"))
        lig <- req(tab("expressed_ligands"), c("ligand"))
        rec <- req(tab("expressed_receptors"), c("receptor"))
        lr <- req(tab("lr_prior"), c("ligand", "receptor"))
        if(anyDuplicated(de$feature_id)||!isTRUE(ctx$resolved_decisions$receiver_table_contains_full_tested_universe))stop("NicheNet receiver background must include the full tested expressed universe")
        potential <- intersect(colnames(prior),intersect(lig$ligand, lr$ligand[lr$receptor %in% rec$receptor]))
        if(!length(potential))stop("No covered ligand remains after receptor and prior-coverage QC")
        background <- intersect(de$feature_id, rownames(prior))
        genes <- intersect(de$feature_id[de$q < p$fdr & de$logFC > p$logfc], background)
        if (length(genes) < p$min_targets) 
            stop("Insufficient receiver target-set coverage")
        act <- nichenetr::predict_ligand_activities(geneset = genes, background_expressed_genes = background, 
            ligand_target_matrix = prior, potential_ligands = potential)
        links <- do.call(rbind, lapply(potential, function(l) data.frame(ligand = l, target = background, 
            weight = prior[background, l])))
        save4(act, links, data.frame(target = background, in_target_set = background %in% genes), lr[lr$ligand %in% 
            potential & lr$receptor %in% rec$receptor, ], list(receiver_genes = length(background), target_genes = length(genes), 
            ligands = length(potential)))
    }
    else if (key == "spatial_variable_genes") {
        need("SPARK")
        x <- mat(counts = TRUE)
        co <- req(tab("coordinates"), c("spot_id", "x", "y", "section_id", "unit_id"))
        if (!identical(colnames(x), co$spot_id)) 
            stop("Spatial axes mismatch")
        results <- list()
        for (section in unique(co$section_id)) {
            ids <- which(co$section_id == section)
            if (length(unique(co$unit_id[ids])) != 1) 
                stop("Section belongs to more than one biological unit")
            v <- x[, ids, drop = FALSE]
            keep <- rowSums(v) >= p$min_counts
            if (length(ids) < 20 || sum(keep) < 2) 
                stop("Insufficient per-section spatial counts")
            r <- SPARK::sparkx(v[keep, , drop = FALSE], as.matrix(co[ids, c("x", "y")]), numCores = p$cores, 
                option = "mixture")
            z <- as.data.frame(r$res_mtest)
            if(!"combinedPval"%in%names(z)||nrow(z)!=sum(keep))stop("SPARK-X raw p-value schema/feature count mismatch")
            z$feature_id <- rownames(v)[keep]
            z$section_id <- section
            z$unit_id <- unique(co$unit_id[ids])
            results[[section]] <- z
        }
        res <- do.call(rbind, results)
        res$joint_family_q<-p.adjust(res$combinedPval,"BH")
        replication<-do.call(rbind,lapply(split(res,res$feature_id),function(v)data.frame(feature_id=v$feature_id[1],sections_tested=nrow(v),independent_units_tested=length(unique(v$unit_id)),independent_units_with_spatial_signal=length(unique(v$unit_id[v$joint_family_q<p$alpha_fdr])),scope="conditional_spatial_evidence_not_population_replication_test")))
        save4(res, co, data.frame(feature_id = rownames(x), total_count = rowSums(x)), replication, list(sections = length(results), 
            units = length(unique(co$unit_id)), gene_section_tests = nrow(res)))
    }
    else if (key == "motif_deviation") {
        need("chromVAR")
        need("SummarizedExperiment")
        need("GenomicRanges")
        x <- mat(counts = TRUE)
        s <- meta()
        x <- aligned(x, s)
        rg <- req(tab("regions"), c("feature_id", "chromosome", "start", "end"))
        if (!identical(rg$feature_id, rownames(x))) 
            stop("Peak region order mismatch")
        gr <- GenomicRanges::GRanges(rg$chromosome, IRanges::IRanges(rg$start+1L, rg$end))
        se <- SummarizedExperiment::SummarizedExperiment(assays = list(counts = x), rowRanges = gr)
        genome <- readRDS(I$genome_rds)
        se <- chromVAR::addGCBias(se, genome = genome)
        matches <- readRDS(I$motif_matches)
        mm <- if (inherits(matches, "SummarizedExperiment")) 
            SummarizedExperiment::assay(matches)
        else matches
        if(!identical(rownames(mm),rownames(x)))stop("Motif match rows do not match exact peak IDs/order")
        retain <- colSums(mm) >= p$min_peaks
        matches <- matches[, retain, drop = FALSE]
        if (!any(retain)) 
            stop("No motif passes peak coverage")
        bg <- chromVAR::getBackgroundPeaks(se)
        dev <- chromVAR::computeDeviations(object = se, annotations = matches, background_peaks = bg)
        scores <- chromVAR::deviationScores(dev)
        f <- fits(scores, s)
        save4(scores, f$result, data.frame(peak_id = rownames(x), bg), data.frame(sample_id = s$sample_id, 
            fragments = colSums(x)), list(peaks = nrow(x), samples = ncol(x), motifs = nrow(scores)))
    }
    else stop(paste("No implementation for", key))
}, warning = function(w) {
    warnings_seen <<- c(warnings_seen, conditionMessage(w))
})
