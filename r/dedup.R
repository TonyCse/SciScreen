# R Script for Literature Review Deduplication
# Alternative deduplication implementation using R
# This script provides an R-based approach for researchers who prefer R

# Load required libraries
suppressPackageStartupMessages({
  library(dplyr)
  library(stringr)
  library(readr)
  library(RecordLinkage)
  library(stringdist)
})

# Function to clean and normalize titles for comparison
normalize_title <- function(title) {
  if (is.na(title) || title == "") return("")
  
  # Convert to lowercase
  title <- tolower(title)
  
  # Remove punctuation and extra spaces
  title <- str_replace_all(title, "[[:punct:]]", " ")
  title <- str_replace_all(title, "\\s+", " ")
  title <- str_trim(title)
  
  return(title)
}

# Function to find exact duplicates by DOI/PMID
find_exact_duplicates <- function(df) {
  cat("Finding exact duplicates...\n")
  
  exact_duplicates <- list()
  
  # Check DOI duplicates
  if ("doi" %in% colnames(df)) {
    doi_dups <- df %>%
      filter(!is.na(doi) & doi != "") %>%
      group_by(doi) %>%
      filter(n() > 1) %>%
      group_split()
    
    if (length(doi_dups) > 0) {
      exact_duplicates <- c(exact_duplicates, doi_dups)
    }
  }
  
  # Check PMID duplicates
  if ("pmid" %in% colnames(df)) {
    pmid_dups <- df %>%
      filter(!is.na(pmid) & pmid != "") %>%
      group_by(pmid) %>%
      filter(n() > 1) %>%
      group_split()
    
    if (length(pmid_dups) > 0) {
      exact_duplicates <- c(exact_duplicates, pmid_dups)
    }
  }
  
  cat(sprintf("Found %d groups of exact duplicates\n", length(exact_duplicates)))
  return(exact_duplicates)
}

# Function to choose best record from duplicates
choose_best_record <- function(dup_group) {
  # Scoring criteria:
  # 1. Has PDF URL (100 points)
  # 2. Abstract length (up to 50 points)
  # 3. Citation count (up to 30 points)
  # 4. Completeness (5 points per complete field)
  
  scores <- rep(0, nrow(dup_group))
  
  for (i in seq_len(nrow(dup_group))) {
    row <- dup_group[i, ]
    
    # PDF URL bonus
    if (!is.na(row$pdf_url) && row$pdf_url != "") {
      scores[i] <- scores[i] + 100
    }
    
    # Abstract length bonus
    if (!is.na(row$abstract)) {
      abstract_len <- nchar(as.character(row$abstract))
      scores[i] <- scores[i] + min(abstract_len / 10, 50)
    }
    
    # Citation count bonus
    if (!is.na(row$cited_by)) {
      scores[i] <- scores[i] + min(as.numeric(row$cited_by) / 10, 30)
    }
    
    # Completeness bonus
    complete_fields <- c("title", "authors", "journal", "year", "doi")
    completeness <- sum(!is.na(row[complete_fields]) & row[complete_fields] != "")
    scores[i] <- scores[i] + completeness * 5
  }
  
  # Return index of best record
  return(which.max(scores))
}

# Function to remove exact duplicates
remove_exact_duplicates <- function(df) {
  cat("Removing exact duplicates...\n")
  
  duplicate_groups <- find_exact_duplicates(df)
  
  if (length(duplicate_groups) == 0) {
    cat("No exact duplicates to remove\n")
    return(list(df = df, removed_count = 0))
  }
  
  # Track rows to remove
  rows_to_remove <- c()
  
  for (dup_group in duplicate_groups) {
    if (nrow(dup_group) > 1) {
      # Find row indices in original dataframe
      group_indices <- which(df$doi %in% dup_group$doi | df$pmid %in% dup_group$pmid)
      
      # Choose best record
      best_idx <- choose_best_record(dup_group)
      best_row_idx <- group_indices[best_idx]
      
      # Mark others for removal
      to_remove <- group_indices[-best_idx]
      rows_to_remove <- c(rows_to_remove, to_remove)
    }
  }
  
  # Remove duplicates
  if (length(rows_to_remove) > 0) {
    cleaned_df <- df[-rows_to_remove, ]
  } else {
    cleaned_df <- df
  }
  
  removed_count <- length(rows_to_remove)
  cat(sprintf("Removed %d exact duplicate records\n", removed_count))
  
  return(list(df = cleaned_df, removed_count = removed_count))
}

# Function to find fuzzy title duplicates
find_fuzzy_duplicates <- function(df, similarity_threshold = 0.85) {
  cat("Finding fuzzy title duplicates...\n")
  
  if (!"title_normalized" %in% colnames(df)) {
    df$title_normalized <- sapply(df$title, normalize_title)
  }
  
  # Remove rows with empty normalized titles
  df_with_titles <- df %>% filter(title_normalized != "")
  
  if (nrow(df_with_titles) < 2) {
    cat("Not enough records with titles for fuzzy matching\n")
    return(list())
  }
  
  # Calculate string distances
  title_distances <- stringdistmatrix(
    df_with_titles$title_normalized,
    method = "jw"  # Jaro-Winkler distance
  )
  
  # Convert distances to similarities
  similarities <- 1 - title_distances
  
  # Find potential duplicates
  fuzzy_groups <- list()
  processed_rows <- c()
  
  for (i in seq_len(nrow(df_with_titles) - 1)) {
    if (i %in% processed_rows) next
    
    # Find similar titles
    similar_indices <- which(similarities[i, ] >= similarity_threshold & 
                           seq_along(similarities[i, ]) != i)
    
    if (length(similar_indices) > 0) {
      # Check year compatibility (within 1 year)
      year_i <- as.numeric(df_with_titles$year[i])
      compatible_indices <- c()
      
      for (j in similar_indices) {
        year_j <- as.numeric(df_with_titles$year[j])
        if (is.na(year_i) || is.na(year_j) || abs(year_i - year_j) <= 1) {
          compatible_indices <- c(compatible_indices, j)
        }
      }
      
      if (length(compatible_indices) > 0) {
        group_indices <- c(i, compatible_indices)
        fuzzy_groups <- append(fuzzy_groups, list(group_indices))
        processed_rows <- c(processed_rows, group_indices)
      }
    }
  }
  
  cat(sprintf("Found %d groups of fuzzy duplicates\n", length(fuzzy_groups)))
  return(fuzzy_groups)
}

# Function to remove fuzzy duplicates
remove_fuzzy_duplicates <- function(df, similarity_threshold = 0.85) {
  cat("Removing fuzzy duplicates...\n")
  
  fuzzy_groups <- find_fuzzy_duplicates(df, similarity_threshold)
  
  if (length(fuzzy_groups) == 0) {
    cat("No fuzzy duplicates to remove\n")
    return(list(df = df, removed_count = 0))
  }
  
  # Track rows to remove
  rows_to_remove <- c()
  
  for (group_indices in fuzzy_groups) {
    if (length(group_indices) > 1) {
      # Get the duplicate group
      dup_group <- df[group_indices, ]
      
      # Choose best record
      best_idx <- choose_best_record(dup_group)
      best_row_idx <- group_indices[best_idx]
      
      # Mark others for removal
      to_remove <- group_indices[-best_idx]
      rows_to_remove <- c(rows_to_remove, to_remove)
    }
  }
  
  # Remove duplicates
  if (length(rows_to_remove) > 0) {
    cleaned_df <- df[-rows_to_remove, ]
  } else {
    cleaned_df <- df
  }
  
  removed_count <- length(rows_to_remove)
  cat(sprintf("Removed %d fuzzy duplicate records\n", removed_count))
  
  return(list(df = cleaned_df, removed_count = removed_count))
}

# Main deduplication function
deduplicate_papers <- function(input_file, output_file = NULL, 
                              similarity_threshold = 0.85) {
  cat("=== R Literature Review Deduplication ===\n")
  cat(sprintf("Input file: %s\n", input_file))
  
  # Read data
  if (str_detect(input_file, "\\.csv$")) {
    df <- read_csv(input_file, show_col_types = FALSE)
  } else {
    stop("Only CSV files are supported")
  }
  
  cat(sprintf("Loaded %d records\n", nrow(df)))
  
  # Add normalized titles
  if (!"title_normalized" %in% colnames(df)) {
    df$title_normalized <- sapply(df$title, normalize_title)
  }
  
  # Step 1: Remove exact duplicates
  result1 <- remove_exact_duplicates(df)
  df_no_exact <- result1$df
  exact_removed <- result1$removed_count
  
  # Step 2: Remove fuzzy duplicates
  result2 <- remove_fuzzy_duplicates(df_no_exact, similarity_threshold)
  df_deduplicated <- result2$df
  fuzzy_removed <- result2$removed_count
  
  # Summary
  total_removed <- exact_removed + fuzzy_removed
  final_count <- nrow(df_deduplicated)
  reduction_pct <- (total_removed / nrow(df)) * 100
  
  cat("\n=== Deduplication Summary ===\n")
  cat(sprintf("Input records: %d\n", nrow(df)))
  cat(sprintf("Exact duplicates removed: %d\n", exact_removed))
  cat(sprintf("Fuzzy duplicates removed: %d\n", fuzzy_removed))
  cat(sprintf("Total removed: %d\n", total_removed))
  cat(sprintf("Final count: %d\n", final_count))
  cat(sprintf("Reduction: %.1f%%\n", reduction_pct))
  
  # Save results
  if (is.null(output_file)) {
    # Generate output filename
    output_file <- str_replace(input_file, "\\.csv$", "_deduplicated.csv")
  }
  
  # Remove normalized title column before saving
  df_output <- df_deduplicated %>% select(-title_normalized)
  write_csv(df_output, output_file)
  
  cat(sprintf("Deduplicated data saved to: %s\n", output_file))
  
  return(list(
    input_count = nrow(df),
    exact_removed = exact_removed,
    fuzzy_removed = fuzzy_removed,
    final_count = final_count,
    output_file = output_file
  ))
}

# Command line interface
if (!interactive()) {
  # Get command line arguments
  args <- commandArgs(trailingOnly = TRUE)
  
  if (length(args) == 0) {
    cat("Usage: Rscript dedup.R input_file.csv [output_file.csv] [similarity_threshold]\n")
    cat("Example: Rscript dedup.R data/raw/papers.csv data/processed/papers_deduplicated.csv 0.85\n")
    quit(status = 1)
  }
  
  input_file <- args[1]
  output_file <- if (length(args) >= 2) args[2] else NULL
  similarity_threshold <- if (length(args) >= 3) as.numeric(args[3]) else 0.85
  
  # Check if input file exists
  if (!file.exists(input_file)) {
    cat(sprintf("Error: Input file '%s' not found\n", input_file))
    quit(status = 1)
  }
  
  # Run deduplication
  tryCatch({
    result <- deduplicate_papers(input_file, output_file, similarity_threshold)
    cat("Deduplication completed successfully!\n")
  }, error = function(e) {
    cat(sprintf("Error: %s\n", e$message))
    quit(status = 1)
  })
}
