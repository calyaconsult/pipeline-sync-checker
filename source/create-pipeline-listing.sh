for dir in unprocessed processing processed; do
    echo "~/$dir"
    ls -l --time-style=long-iso ~/$dir
    echo
done
